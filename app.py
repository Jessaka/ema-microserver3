from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal

from kalkulacka import (
    InvestmentType,
    LumpSumInput,
    RentaInput,
    compute_lump_sum,
    compute_renta,
)

app = FastAPI()


class CalcRequest(BaseModel):
    # Varianta: studia/bydlení/... = "lump_sum", důchod = "renta"
    goal_type: Literal["lump_sum", "renta"]

    # Způsob investování
    investment_type: Literal["one_time", "monthly", "combined"]

    # Volitelné – jednorázová investice pro "combined"
    one_time_investment: Optional[float] = 0.0

    # ---- pro lump_sum ----
    target_amount: Optional[float] = None
    years: Optional[float] = None
    annual_rate_accum: Optional[float] = None

    # ---- pro renta ----
    monthly_rent: Optional[float] = None
    years_rent: Optional[float] = None
    annual_rate_rent: Optional[float] = None
    years_saving: Optional[float] = None
    # annual_rate_accum se používá i u renty (akumulace) -> je už nahoře


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/calc")
def calc(req: CalcRequest):
    try:
        inv_type = InvestmentType(req.investment_type)

        if req.goal_type == "lump_sum":
            missing = [k for k in ["target_amount", "years", "annual_rate_accum"] if getattr(req, k) is None]
            if missing:
                raise HTTPException(status_code=400, detail=f"Missing fields for lump_sum: {missing}")

            inp = LumpSumInput(
                target_amount=req.target_amount,
                years=req.years,
                annual_rate_accum=req.annual_rate_accum,
                investment_type=inv_type,
                one_time_investment=req.one_time_investment or 0.0,
            )
            return compute_lump_sum(inp)

        if req.goal_type == "renta":
            missing = [k for k in ["monthly_rent", "years_rent", "annual_rate_rent", "years_saving", "annual_rate_accum"]
                       if getattr(req, k) is None]
            if missing:
                raise HTTPException(status_code=400, detail=f"Missing fields for renta: {missing}")

            inp = RentaInput(
                monthly_rent=req.monthly_rent,
                years_rent=req.years_rent,
                annual_rate_rent=req.annual_rate_rent,
                years_saving=req.years_saving,
                annual_rate_accum=req.annual_rate_accum,
                investment_type=inv_type,
                one_time_investment=req.one_time_investment or 0.0,
            )
            return compute_renta(inp)

        raise HTTPException(status_code=400, detail="Unknown goal_type")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
