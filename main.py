from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, List, Optional

import psycopg2
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel


# Carica variabili d'ambiente da .env (se presente)
load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL non impostata. Imposta la variabile d'ambiente, "
        "ad esempio: postgresql://user:password@localhost:5432/trading_db",
    )


@contextmanager
def get_connection():
    """Context manager che restituisce una connessione PostgreSQL.

    Usa il DSN in DATABASE_URL.
    """

    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()


# =====================
# Modelli di risposta API
# =====================


class BalancePoint(BaseModel):
    timestamp: datetime
    balance_usd: float


class OpenPosition(BaseModel):
    id: int
    snapshot_id: int
    symbol: str
    side: str
    size: float
    entry_price: Optional[float]
    mark_price: Optional[float]
    pnl_usd: Optional[float]
    leverage: Optional[str]
    snapshot_created_at: datetime


class ClosedPosition(BaseModel):
    symbol: str
    side: str
    entry_price: float
    exit_price: float
    pnl_usd: float
    opened_at: datetime
    closed_at: datetime
    leverage: Optional[str]


class BotOperation(BaseModel):
    id: int
    created_at: datetime
    operation: str
    symbol: Optional[str]
    direction: Optional[str]
    target_portion_of_balance: Optional[float]
    leverage: Optional[float]
    raw_payload: Any
    system_prompt: Optional[str]
    # Dati tecnici aggiuntivi (da indicators_contexts e forecasts_contexts)
    rsi_7: Optional[float] = None
    macd: Optional[float] = None
    current_price: Optional[float] = None
    predicted_price: Optional[float] = None
    forecast_lower: Optional[float] = None
    forecast_upper: Optional[float] = None


# =====================
# App FastAPI + Template Jinja2
# =====================


app = FastAPI(
    title="Trading Agent Dashboard API",
    description=(
        "API per leggere i dati del trading agent dal database Postgres: "
        "saldo nel tempo, posizioni aperte, operazioni del bot con full prompt."
    ),
    version="0.3.1",
)

templates = Jinja2Templates(directory="templates")


# =====================
# Endpoint API JSON
# =====================


@app.get("/balance", response_model=List[BalancePoint])
def get_balance() -> List[BalancePoint]:
    """Restituisce TUTTA la storia del saldo (balance_usd) ordinata nel tempo.

    I dati sono presi dalla tabella `account_snapshots`.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT created_at, balance_usd
                FROM account_snapshots
                ORDER BY created_at ASC;
                """
            )
            rows = cur.fetchall()

    return [
        BalancePoint(timestamp=row[0], balance_usd=float(row[1]))
        for row in rows
    ]


@app.get("/open-positions", response_model=List[OpenPosition])
def get_open_positions() -> List[OpenPosition]:
    """Restituisce le posizioni aperte dell'ULTIMO snapshot disponibile.

    - Prende l'ultimo record da `account_snapshots`.
    - Recupera le posizioni corrispondenti da `open_positions`.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Ultimo snapshot
            cur.execute(
                """
                SELECT id, created_at
                FROM account_snapshots
                ORDER BY created_at DESC
                LIMIT 1;
                """
            )
            row = cur.fetchone()
            if not row:
                return []
            snapshot_id = row[0]
            snapshot_created_at = row[1]

            # Posizioni aperte per quello snapshot
            cur.execute(
                """
                SELECT
                    id,
                    snapshot_id,
                    symbol,
                    side,
                    size,
                    entry_price,
                    mark_price,
                    pnl_usd,
                    leverage
                FROM open_positions
                WHERE snapshot_id = %s
                ORDER BY symbol ASC, id ASC;
                """,
                (snapshot_id,),
            )
            rows = cur.fetchall()

    return [
        OpenPosition(
            id=row[0],
            snapshot_id=row[1],
            symbol=row[2],
            side=row[3],
            size=float(row[4]),
            entry_price=float(row[5]) if row[5] is not None else None,
            mark_price=float(row[6]) if row[6] is not None else None,
            pnl_usd=float(row[7]) if row[7] is not None else None,
            leverage=row[8],
            snapshot_created_at=snapshot_created_at,
        )
        for row in rows
    ]


@app.get("/closed-positions", response_model=List[ClosedPosition])
def get_closed_positions() -> List[ClosedPosition]:
    """Calcola le posizioni chiuse confrontando gli snapshot consecutivi.
    
    Logica:
    - Se una posizione esiste in T ma non in T+1, è stata chiusa.
    - Il PnL realizzato è l'ultimo PnL registrato in T.
    """
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Recuperiamo tutti gli snapshot con le loro posizioni
            # Usiamo una query che ci dia snapshot_id, created_at e il json delle posizioni
            cur.execute(
                """
                SELECT 
                    s.id, 
                    s.created_at,
                    op.symbol,
                    op.side,
                    op.entry_price,
                    op.mark_price,
                    op.pnl_usd,
                    op.leverage
                FROM account_snapshots s
                JOIN open_positions op ON s.id = op.snapshot_id
                ORDER BY s.created_at ASC;
                """
            )
            rows = cur.fetchall()

    # Organizziamo i dati per snapshot
    snapshots_map = {}
    for row in rows:
        snap_id = row[0]
        created_at = row[1]
        
        if snap_id not in snapshots_map:
            snapshots_map[snap_id] = {
                'created_at': created_at,
                'positions': {}
            }
        
        # Chiave univoca per la posizione: Symbol + Side
        # (assumiamo che non ci siano due posizioni opposte sullo stesso simbolo nello stesso momento, 
        # o se ci sono, il bot le gestisce come hedge mode, ma per ora semplifichiamo)
        pos_key = f"{row[2]}_{row[3]}"
        
        snapshots_map[snap_id]['positions'][pos_key] = {
            'symbol': row[2],
            'side': row[3],
            'entry_price': float(row[4]) if row[4] is not None else 0,
            'mark_price': float(row[5]) if row[5] is not None else 0,
            'pnl_usd': float(row[6]) if row[6] is not None else 0,
            'leverage': row[7]
        }

    # Ordiniamo gli snapshot per data
    sorted_snap_ids = sorted(snapshots_map.keys(), key=lambda k: snapshots_map[k]['created_at'])
    
    closed_positions = []
    position_start_times = {} # key -> datetime (quando è stata vista la prima volta)

    # Iteriamo su tutti gli snapshot
    for i in range(len(sorted_snap_ids)):
        curr_id = sorted_snap_ids[i]
        curr_snap = snapshots_map[curr_id]
        curr_positions = curr_snap['positions']
        curr_time = curr_snap['created_at']

        # 1. Registriamo data inizio per nuove posizioni
        for pos_key in curr_positions:
            if pos_key not in position_start_times:
                position_start_times[pos_key] = curr_time
        
        # 2. Se non è l'ultimo snapshot, cerchiamo le chiusure confrontando con il successivo
        if i < len(sorted_snap_ids) - 1:
            next_id = sorted_snap_ids[i+1]
            next_snap = snapshots_map[next_id]
            next_positions = next_snap['positions']
            next_time = next_snap['created_at']
            
            # Cerchiamo posizioni che sono in curr ma NON in next
            for pos_key, pos_data in curr_positions.items():
                if pos_key not in next_positions:
                    # Trovata posizione chiusa!
                    opened_at = position_start_times.get(pos_key, curr_time)
                    
                    closed_positions.append(ClosedPosition(
                        symbol=pos_data['symbol'],
                        side=pos_data['side'],
                        entry_price=pos_data['entry_price'],
                        exit_price=pos_data['mark_price'],
                        pnl_usd=pos_data['pnl_usd'],
                        opened_at=opened_at,
                        closed_at=next_time,
                        leverage=pos_data['leverage']
                    ))
                    
                    # Rimuoviamo dal tracking perché è chiusa
                    if pos_key in position_start_times:
                        del position_start_times[pos_key]
    
    # Ordiniamo le posizioni chiuse dalla più recente
    closed_positions.sort(key=lambda x: x.closed_at, reverse=True)
    
    return closed_positions


@app.get("/bot-operations", response_model=List[BotOperation])
def get_bot_operations(
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Numero massimo di operazioni da restituire (default 50)",
    ),
) -> List[BotOperation]:
    """Restituisce le ULTIME `limit` operazioni del bot con il full system prompt.

    - I dati provengono da `bot_operations` uniti a `ai_contexts`.
    - Ordinati da più recente a meno recente.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    bo.id,
                    bo.created_at,
                    bo.operation,
                    bo.symbol,
                    bo.direction,
                    bo.target_portion_of_balance,
                    bo.leverage,
                    bo.raw_payload,
                    ac.system_prompt,
                    -- Indicators (match su context_id e symbol/ticker)
                    ic.rsi_7,
                    ic.macd,
                    ic.price,
                    -- Forecasts (match su context_id e symbol/ticker)
                    fc.prediction,
                    fc.lower_bound,
                    fc.upper_bound
                FROM bot_operations AS bo
                LEFT JOIN ai_contexts AS ac ON bo.context_id = ac.id
                LEFT JOIN indicators_contexts AS ic ON bo.context_id = ic.context_id AND bo.symbol = ic.ticker
                LEFT JOIN forecasts_contexts AS fc ON bo.context_id = fc.context_id AND bo.symbol = fc.ticker
                ORDER BY bo.created_at DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

    operations: List[BotOperation] = []
    for row in rows:
        operations.append(
            BotOperation(
                id=row[0],
                created_at=row[1],
                operation=row[2],
                symbol=row[3],
                direction=row[4],
                target_portion_of_balance=float(row[5]) if row[5] is not None else None,
                leverage=float(row[6]) if row[6] is not None else None,
                raw_payload=row[7],
                system_prompt=row[8],
                rsi_7=float(row[9]) if row[9] is not None else None,
                macd=float(row[10]) if row[10] is not None else None,
                current_price=float(row[11]) if row[11] is not None else None,
                predicted_price=float(row[12]) if row[12] is not None else None,
                forecast_lower=float(row[13]) if row[13] is not None else None,
                forecast_upper=float(row[14]) if row[14] is not None else None,
            )
        )

    return operations


# =====================
# Endpoint HTML + HTMX
# =====================


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Dashboard principale HTML."""

    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/ui/balance", response_class=HTMLResponse)
async def ui_balance(request: Request) -> HTMLResponse:
    """Partial HTML con il grafico del saldo nel tempo."""

    points = get_balance()
    labels = [p.timestamp.isoformat() for p in points]
    values = [p.balance_usd for p in points]
    return templates.TemplateResponse(
        "partials/balance_table.html",
        {"request": request, "labels": labels, "values": values},
    )


@app.get("/ui/open-positions", response_class=HTMLResponse)
async def ui_open_positions(request: Request) -> HTMLResponse:
    """Partial HTML con le posizioni aperte (ultimo snapshot)."""

    positions = get_open_positions()
    return templates.TemplateResponse(
        "partials/open_positions_table.html",
        {"request": request, "positions": positions},
    )


@app.get("/ui/bot-operations", response_class=HTMLResponse)
async def ui_bot_operations(request: Request) -> HTMLResponse:
    """Partial HTML con le ultime operazioni del bot."""

    operations = get_bot_operations(limit=10)
    return templates.TemplateResponse(
        "partials/bot_operations_table.html",
        {"request": request, "operations": operations},
    )


@app.get("/ui/closed-positions", response_class=HTMLResponse)
async def ui_closed_positions(request: Request) -> HTMLResponse:
    """Partial HTML con lo storico delle posizioni chiuse e statistiche."""

    positions = get_closed_positions()
    
    # Data split per versione 0.0.2
    split_date = datetime(2025, 12, 5).date()
    
    # --- Split Positions ---
    # Usiamo opened_at per decidere la versione
    current_positions = [p for p in positions if p.opened_at.date() >= split_date]
    archive_positions = [p for p in positions if p.opened_at.date() < split_date]
    
    def calculate_stats(pos_list):
        total = len(pos_list)
        wins = len([p for p in pos_list if p.pnl_usd > 0])
        losses = total - wins
        win_rate = (wins / total * 100) if total > 0 else 0
        return {
            "total": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(win_rate, 1)
        }

    current_stats = calculate_stats(current_positions)
    archive_stats = calculate_stats(archive_positions)

    # Limitiamo a 20 per la visualizzazione della lista per ogni sezione
    return templates.TemplateResponse(
        "partials/closed_positions_table.html",
        {
            "request": request, 
            "current_positions": current_positions[:20],
            "archive_positions": archive_positions[:20],
            "current_stats": current_stats,
            "archive_stats": archive_stats
        },
    )


@app.get("/ui/pnl-stats", response_class=HTMLResponse)
async def ui_pnl_stats(request: Request) -> HTMLResponse:
    """Partial HTML con le statistiche di PnL (infografica)."""

    points = get_balance()
    
    if not points:
        return templates.TemplateResponse(
            "partials/pnl_stats.html",
            {
                "request": request,
                "current_stats": None,
                "archive_stats": None,
                "has_data": False
            },
        )

    # Data split per versione 0.0.2
    # Usiamo una data naive o aware a seconda di come arrivano dal DB, 
    # ma per sicurezza convertiamo tutto a naive per il confronto o gestiamo la timezone.
    # Assumiamo che il DB restituisca datetime.
    split_date = datetime(2025, 12, 5).date()

    # --- Calcolo Stats Archivio (v0.0.1) ---
    # Tutti i punti PRIMA del 5/12/2025
    archive_points = [p for p in points if p.timestamp.date() < split_date]
    
    archive_stats = None
    if archive_points:
        initial_balance_old = archive_points[0].balance_usd
        final_balance_old = archive_points[-1].balance_usd
        pnl_usd_old = final_balance_old - initial_balance_old
        pnl_percent_old = (pnl_usd_old / initial_balance_old * 100) if initial_balance_old != 0 else 0
        
        archive_stats = {
            "initial_balance": initial_balance_old,
            "current_balance": final_balance_old,
            "pnl_usd": pnl_usd_old,
            "pnl_percent": pnl_percent_old,
        }

    # --- Calcolo Stats Correnti (v0.0.2) ---
    # Tutti i punti DAL 5/12/2025 in poi
    # Equity iniziale forzata a 1032$ come richiesto
    current_points = [p for p in points if p.timestamp.date() >= split_date]
    
    current_stats = None
    if current_points:
        initial_balance_new = 1032.0
        current_balance_new = current_points[-1].balance_usd
        pnl_usd_new = current_balance_new - initial_balance_new
        pnl_percent_new = (pnl_usd_new / initial_balance_new * 100) if initial_balance_new != 0 else 0
        
        current_stats = {
            "initial_balance": initial_balance_new,
            "current_balance": current_balance_new,
            "pnl_usd": pnl_usd_new,
            "pnl_percent": pnl_percent_new,
        }
    else:
        # Se non ci sono ancora dati per la nuova versione, mostriamo comunque l'iniziale
        current_stats = {
            "initial_balance": 1032.0,
            "current_balance": 1032.0,
            "pnl_usd": 0.0,
            "pnl_percent": 0.0,
        }

    return templates.TemplateResponse(
        "partials/pnl_stats.html",
        {
            "request": request,
            "current_stats": current_stats,
            "archive_stats": archive_stats,
            "has_data": True
        },
    )


# Comodo per sviluppo locale: `python main.py`
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
