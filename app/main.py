from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import qrcode
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.algorithms import apply_transfers
from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import Group, Member, Settlement
from app.schemas import ExpenseCreate, SettlementCreate
from app.services import REQUIRED_FILES, add_expense, dashboard_data, export_balances, group_balances, import_dataset


app = FastAPI(title="SplitUZ", version="1.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
MAX_UPLOAD_FILE_BYTES = 10 * 1024 * 1024
MAX_UPLOAD_TOTAL_BYTES = 40 * 1024 * 1024


@app.middleware("http")
async def security_headers(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and (origin := request.headers.get("origin")):
        expected_origin = f"{request.url.scheme}://{request.url.netloc}"
        if origin.rstrip("/") != expected_origin.rstrip("/"):
            return Response("Cross-site request rejected", status_code=403, media_type="text/plain")
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        dataset_ready = all((settings.dataset_dir / filename).is_file() for filename in REQUIRED_FILES)
        if dataset_ready:
            # Mounted CSV files are the source of truth on every judge/fresh run.
            import_dataset(db, settings.dataset_dir)
        else:
            raise RuntimeError(f"Dataset is incomplete in {settings.dataset_dir}")
        export_balances(db, settings.result_dir / "balanslar.csv")


@app.get("/health")
def health(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Database unavailable") from exc
    return {"status": "ok", "database": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    groups = db.execute(select(Group).order_by(Group.id)).scalars().all()
    return templates.TemplateResponse(request, "index.html", {"groups": groups})


@app.get("/api/groups")
def groups(db: Session = Depends(get_db)):
    rows = db.execute(select(Group).order_by(Group.id)).scalars().all()
    return [{"id": row.id, "name": row.name, "currency": row.currency} for row in rows]


@app.get("/api/groups/{group_id}/members")
def members(group_id: str, db: Session = Depends(get_db)):
    rows = db.execute(select(Member).where(Member.group_id == group_id).order_by(Member.id)).scalars().all()
    if not rows:
        raise HTTPException(404, "Group not found or empty")
    return [{"id": row.id, "name": row.name, "bank": row.bank} for row in rows]


@app.get("/api/dashboard")
def dashboard(group_id: str, member_id: str, db: Session = Depends(get_db)):
    try:
        data = dashboard_data(db, group_id, member_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    optimization = data["optimized"]
    transfers = optimization.transfers
    assert all(value == 0 for value in apply_transfers(data["balances"], transfers).values())
    return {
        "member_balance": data["member_balance"],
        "balances": [{"member_id": key, "name": data["names"][key], "amount": value} for key, value in data["balances"].items()],
        "transfers": [{"sender_id": t.sender_id, "sender": data["names"][t.sender_id], "receiver_id": t.receiver_id, "receiver": data["names"][t.receiver_id], "amount": t.amount} for t in transfers],
        "greedy_count": len(data["greedy"]),
        "optimized_count": len(transfers),
        "is_exact": optimization.is_exact,
        "optimization_reason": optimization.reason,
    }


@app.post("/api/expenses", status_code=201)
def create_expense(payload: ExpenseCreate, db: Session = Depends(get_db)):
    try:
        expense_id = add_expense(db, payload.group_id, payload.paid_by, payload.amount, payload.category, payload.note, payload.method, payload.participants, payload.values)
        export_balances(db, settings.result_dir / "balanslar.csv")
        return {"expense_id": expense_id}
    except (ValueError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/settlements", status_code=201)
def create_settlement(payload: SettlementCreate, db: Session = Depends(get_db)):
    group = db.execute(select(Group).where(Group.id == payload.group_id).with_for_update()).scalar_one_or_none()
    if group is None:
        raise HTTPException(404, f"Unknown group: {payload.group_id}")
    members = set(db.execute(select(Member.id).where(Member.group_id == payload.group_id)).scalars())
    if payload.sender_id not in members or payload.receiver_id not in members or payload.sender_id == payload.receiver_id:
        raise HTTPException(400, "Invalid settlement participants")
    row = Settlement(id=f"UI-{uuid4().hex}", group_id=payload.group_id, sender_id=payload.sender_id, receiver_id=payload.receiver_id, amount=payload.amount, settled_at=date.today(), status="tasdiqlangan")
    db.add(row)
    db.commit()
    export_balances(db, settings.result_dir / "balanslar.csv")
    return {"settlement_id": row.id}


@app.post("/api/import")
async def upload_dataset(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    names = {file.filename for file in files if file.filename}
    if len(files) != len(REQUIRED_FILES) or len(names) != len(files) or names != set(REQUIRED_FILES):
        raise HTTPException(400, f"Expected exactly: {sorted(REQUIRED_FILES)}")
    try:
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            total_size = 0
            for upload in files:
                file_size = 0
                with (folder / str(upload.filename)).open("wb") as output:
                    while chunk := await upload.read(1024 * 1024):
                        file_size += len(chunk)
                        total_size += len(chunk)
                        if file_size > MAX_UPLOAD_FILE_BYTES or total_size > MAX_UPLOAD_TOTAL_BYTES:
                            raise ValueError("CSV upload exceeds the allowed size")
                        output.write(chunk)
            counts = import_dataset(db, folder)
        export_balances(db, settings.result_dir / "balanslar.csv")
        return counts
    except (ValueError, UnicodeError, OSError, IntegrityError) as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/export")
def download_results(db: Session = Depends(get_db)):
    path = settings.result_dir / "balanslar.csv"
    export_balances(db, path)
    return FileResponse(path, media_type="text/csv", filename="balanslar.csv")


@app.get("/api/qr")
def payment_qr(sender: str = Query(...), receiver: str = Query(...), amount: int = Query(..., gt=0), bank: str = Query("DEMO")):
    payload = f"SPLITUZ|v=1|from={sender}|to={receiver}|amount={amount}|currency=UZS|bank={bank}|demo=true"
    image = qrcode.make(payload)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png", headers={"X-Demo-Payment": "true"})
