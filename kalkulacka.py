"""
kalkulacka.py
Finanční kalkulačka pro Emu + konzolové rozhraní.

- počítá jednorázový cíl (FV) z měsíčního vkladu / jednorázově / kombinace
- počítá rentu (potřebný majetek + jak ho nainvestovat)
- umí běžet ve 2 režimech:
    1) testy (předpřipravené příklady)
    2) interaktivní zadávání z konzole
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict


# ==========================
# Pomocné typy
# ==========================

class GoalType(str, Enum):
    LUMP_SUM = "lump_sum"        # jednorázový cíl
    RENTA = "renta"              # renta / důchod


class InvestmentType(str, Enum):
    ONE_TIME = "one_time"        # jednorázová investice
    MONTHLY = "monthly"          # měsíční investice
    COMBINED = "combined"        # kombinace


@dataclass
class LumpSumInput:
    """Vstupy pro jednorázový cíl (např. 1 mil. za 20 let)."""
    target_amount: float              # cílová částka FV
    years: float                      # horizont v letech
    annual_rate_accum: float          # roční zhodnocení v akumulaci p_a1 (např. 0.07)
    investment_type: InvestmentType   # typ investice
    one_time_investment: float = 0.0  # jednorázová investice dnes (pro kombinaci)


@dataclass
class RentaInput:
    """Vstupy pro rentu / důchod."""
    monthly_rent: float               # požadovaná měsíční renta R
    years_rent: float                 # doba čerpání renty v letech
    annual_rate_rent: float           # roční zhodnocení v období čerpání p_a2
    years_saving: float               # doba akumulace v letech
    annual_rate_accum: float          # roční zhodnocení v akumulaci p_a1
    investment_type: InvestmentType   # typ investice
    one_time_investment: float = 0.0  # jednorázová investice dnes (pro kombinaci)


# ==========================
# Základní matematika
# ==========================

def eff_monthly_rate(annual_rate: float) -> float:
    """
    Efektivní měsíční úroková sazba:
    i = (1 + p_a)^(1/12) - 1
    """
    return (1.0 + annual_rate) ** (1.0 / 12.0) - 1.0


def fv_lump_sum(pv: float, i: float, n_months: int) -> float:
    """Budoucí hodnota jednorázové investice."""
    return pv * (1.0 + i) ** n_months


def pv_from_fv(fv: float, i: float, n_months: int) -> float:
    """Současná hodnota – kolik je potřeba investovat dnes."""
    return fv / ((1.0 + i) ** n_months)


def fv_annuity(monthly_payment: float, i: float, n_months: int) -> float:
    """Budoucí hodnota měsíčních vkladů (anuita)."""
    if i == 0:
        return monthly_payment * n_months
    return monthly_payment * ((1.0 + i) ** n_months - 1.0) / i


def annuity_from_fv(fv: float, i: float, n_months: int) -> float:
    """Reverzní výpočet – jaká měsíční investice vede na cílovou budoucí hodnotu."""
    if i == 0:
        return fv / n_months
    return fv * i / ((1.0 + i) ** n_months - 1.0)


def pv_renta_required(monthly_rent: float, annual_rate_rent: float, years_rent: float) -> float:
    """
    Potřebný majetek na začátku renty, aby šla čerpat měsíční renta R po daný počet let.

    PV_renta = R * (1 - (1 + i2)^(-n)) / i2
    kde i2 je efektivní měsíční sazba v období čerpání.
    """
    i2 = eff_monthly_rate(annual_rate_rent)
    n = int(round(years_rent * 12))
    if i2 == 0:
        return monthly_rent * n
    return monthly_rent * (1.0 - (1.0 + i2) ** (-n)) / i2


# ==========================
# Výpočty pro jednorázový cíl
# ==========================

def compute_lump_sum(input_data: LumpSumInput) -> Dict[str, Any]:
    """
    Spočítá plán pro jednorázový cíl.
    Vrací slovník s klíči:
    - "target_amount"
    - "required_wealth_today" (ONE_TIME)
    - "monthly_investment" (MONTHLY / COMBINED)
    - "one_time_investment" (COMBINED)
    """
    i = eff_monthly_rate(input_data.annual_rate_accum)
    n = int(round(input_data.years * 12))

    result: Dict[str, Any] = {
        "goal_type": "lump_sum",
        "target_amount": input_data.target_amount,
        "years": input_data.years,
        "annual_rate_accum": input_data.annual_rate_accum,
        "investment_type": input_data.investment_type.value
    }

    if input_data.investment_type == InvestmentType.ONE_TIME:
        pv_needed = pv_from_fv(input_data.target_amount, i, n)
        result["required_wealth_today"] = pv_needed

    elif input_data.investment_type == InvestmentType.MONTHLY:
        monthly = annuity_from_fv(input_data.target_amount, i, n)
        result["monthly_investment"] = monthly

    elif input_data.investment_type == InvestmentType.COMBINED:
        fv_one_time = fv_lump_sum(input_data.one_time_investment, i, n)
        remaining = input_data.target_amount - fv_one_time
        if remaining < 0:
            remaining = 0.0
        monthly = annuity_from_fv(remaining, i, n)
        result["one_time_investment"] = input_data.one_time_investment
        result["monthly_investment"] = monthly
        result["fv_one_time_investment"] = fv_one_time
        result["target_amount_remaining_for_monthly"] = remaining

    return result


# ==========================
# Výpočty pro rentu
# ==========================

def compute_renta(input_data: RentaInput) -> Dict[str, Any]:
    """
    Spočítá plán pro rentu.

    Krok 1: zjistíme potřebný majetek na začátku renty (PV_renta).
    Krok 2: zjistíme, jak tento majetek nainvestovat (jednorázově, měsíčně, kombinovaně).
    """
    required_wealth_at_rent_start = pv_renta_required(
        monthly_rent=input_data.monthly_rent,
        annual_rate_rent=input_data.annual_rate_rent,
        years_rent=input_data.years_rent,
    )

    i1 = eff_monthly_rate(input_data.annual_rate_accum)
    m = int(round(input_data.years_saving * 12))

    result: Dict[str, Any] = {
        "goal_type": "renta",
        "monthly_rent": input_data.monthly_rent,
        "years_rent": input_data.years_rent,
        "annual_rate_rent": input_data.annual_rate_rent,
        "years_saving": input_data.years_saving,
        "annual_rate_accum": input_data.annual_rate_accum,
        "investment_type": input_data.investment_type.value,
        "required_wealth_at_rent_start": required_wealth_at_rent_start,
    }

    if input_data.investment_type == InvestmentType.ONE_TIME:
        pv_today = pv_from_fv(required_wealth_at_rent_start, i1, m)
        result["required_wealth_today"] = pv_today

    elif input_data.investment_type == InvestmentType.MONTHLY:
        monthly = annuity_from_fv(required_wealth_at_rent_start, i1, m)
        result["monthly_investment"] = monthly

    elif input_data.investment_type == InvestmentType.COMBINED:
        fv_one_time = fv_lump_sum(input_data.one_time_investment, i1, m)
        remaining = required_wealth_at_rent_start - fv_one_time
        if remaining < 0:
            remaining = 0.0
        monthly = annuity_from_fv(remaining, i1, m)
        result["one_time_investment"] = input_data.one_time_investment
        result["monthly_investment"] = monthly
        result["fv_one_time_investment"] = fv_one_time
        result["target_amount_remaining_for_monthly"] = remaining

    return result


# ==========================
# Pomocné funkce pro výpis a input
# ==========================

def pretty(num: float) -> str:
    """Hezké zaokrouhlení na celé Kč pro výpis."""
    return f"{num:,.0f}".replace(",", " ")


def ask_float(prompt: str) -> float:
    """Bezpečné načtení čísla z konzole. Umí tečku i čárku."""
    while True:
        raw = input(prompt + " ")
        raw = raw.strip().replace(" ", "").replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            print("Zadejte prosím číslo (např. 100000 nebo 7.5).")


def ask_choice(prompt: str, choices: Dict[str, str]) -> str:
    """
    Jednoduché menu – choices je dict {"1": "text", "2": "text"...}
    Vrátí klíč, který si uživatel vybral.
    """
    print(prompt)
    for key, label in choices.items():
        print(f"  {key}) {label}")
    while True:
        ans = input("Vaše volba: ").strip()
        if ans in choices:
            return ans
        print("Neplatná volba, zkuste to znovu.")


# ==========================
# Interaktivní režim – zadávání z konzole
# ==========================

def interactive_lump_sum():
    print("\n=== Jednorázový cíl (cílová částka v budoucnu) ===")
    target = ask_float("Jak velkou cílovou částku chcete mít (v Kč)?")
    years = ask_float("Za kolik let ji chcete mít?")
    rate_percent = ask_float("Jaké roční zhodnocení očekáváte (v %)?")
    rate = rate_percent / 100.0

    inv_choice = ask_choice(
        "Jak chcete investovat?",
        {
            "1": "Jednorázově dnes",
            "2": "Pravidelně měsíčně",
            "3": "Kombinace – část jednorázově, zbytek měsíčně",
        },
    )

    if inv_choice == "1":
        inv_type = InvestmentType.ONE_TIME
        one_time = 0.0
    elif inv_choice == "2":
        inv_type = InvestmentType.MONTHLY
        one_time = 0.0
    else:
        inv_type = InvestmentType.COMBINED
        one_time = ask_float("Jakou částku chcete investovat jednorázově dnes (v Kč)?")

    data = LumpSumInput(
        target_amount=target,
        years=years,
        annual_rate_accum=rate,
        investment_type=inv_type,
        one_time_investment=one_time,
    )
    res = compute_lump_sum(data)

    print("\n--- Výsledek ---")
    print(f"Cílová částka: {pretty(target)} Kč za {years:.1f} roku/let.")
    print(f"Očekávané roční zhodnocení v akumulaci: {rate_percent:.2f} %.")

    if inv_type == InvestmentType.ONE_TIME:
        print(f"Potřebná jednorázová investice dnes: {pretty(res['required_wealth_today'])} Kč")
    elif inv_type == InvestmentType.MONTHLY:
        print(f"Potřebná měsíční investice: {pretty(res['monthly_investment'])} Kč")
    else:
        print(f"Jednorázová investice dnes: {pretty(one_time)} Kč")
        print(f"Odhadovaná budoucí hodnota této jednorázové investice: {pretty(res['fv_one_time_investment'])} Kč")
        print(f"Zbývající část cíle pro měsíční investice: {pretty(res['target_amount_remaining_for_monthly'])} Kč")
        print(f"Potřebná měsíční investice: {pretty(res['monthly_investment'])} Kč")


def interactive_renta():
    print("\n=== Renta / důchod ===")
    monthly_rent = ask_float("Jak vysokou měsíční rentu chcete pobírat (v Kč)?")
    years_rent = ask_float("Jak dlouho chcete rentu pobírat (v letech)?")
    rate_rent_percent = ask_float("Jaké roční zhodnocení očekáváte v období čerpání renty (v %)?")
    rate_rent = rate_rent_percent / 100.0

    years_saving = ask_float("Jak dlouho chcete před tím investovat (v letech)?")
    rate_accum_percent = ask_float("Jaké roční zhodnocení očekáváte v období investování (v %)?")
    rate_accum = rate_accum_percent / 100.0

    inv_choice = ask_choice(
        "Jak chcete investovat na vytvoření tohoto majetku?",
        {
            "1": "Jednorázově dnes",
            "2": "Pravidelně měsíčně",
            "3": "Kombinace – část jednorázově, zbytek měsíčně",
        },
    )

    if inv_choice == "1":
        inv_type = InvestmentType.ONE_TIME
        one_time = 0.0
    elif inv_choice == "2":
        inv_type = InvestmentType.MONTHLY
        one_time = 0.0
    else:
        inv_type = InvestmentType.COMBINED
        one_time = ask_float("Jakou částku chcete investovat jednorázově dnes (v Kč)?")

    data = RentaInput(
        monthly_rent=monthly_rent,
        years_rent=years_rent,
        annual_rate_rent=rate_rent,
        years_saving=years_saving,
        annual_rate_accum=rate_accum,
        investment_type=inv_type,
        one_time_investment=one_time,
    )
    res = compute_renta(data)

    print("\n--- Výsledek ---")
    print(f"Požadovaná měsíční renta: {pretty(monthly_rent)} Kč po dobu {years_rent:.1f} roku/let.")
    print(f"Zhodnocení v období čerpání: {rate_rent_percent:.2f} % p.a.")
    print(f"Zhodnocení v období investování: {rate_accum_percent:.2f} % p.a.")
    print(f"Potřebný majetek na začátku renty: {pretty(res['required_wealth_at_rent_start'])} Kč")

    if inv_type == InvestmentType.ONE_TIME:
        print(f"Potřebná jednorázová investice dnes: {pretty(res['required_wealth_today'])} Kč")
    elif inv_type == InvestmentType.MONTHLY:
        print(f"Potřebná měsíční investice: {pretty(res['monthly_investment'])} Kč")
    else:
        print(f"Jednorázová investice dnes: {pretty(one_time)} Kč")
        print(f"Odhadovaná budoucí hodnota této jednorázové investice: {pretty(res['fv_one_time_investment'])} Kč")
        print(f"Zbývající část cíle pro měsíční investice: {pretty(res['target_amount_remaining_for_monthly'])} Kč")
        print(f"Potřebná měsíční investice: {pretty(res['monthly_investment'])} Kč")


def interactive_cli():
    """Úvodní menu pro ruční zadávání."""
    print("\n=== FINANČNÍ KALKULAČKA – INTERAKTIVNÍ REŽIM ===")
    choice = ask_choice(
        "Co chcete spočítat?",
        {
            "1": "Jednorázový cíl (cílová částka v budoucnu)",
            "2": "Renta / důchod",
        },
    )
    if choice == "1":
        interactive_lump_sum()
    else:
        interactive_renta()


# ==========================
# Manuální testy (příklady z mailů)
# ==========================

def run_manual_tests():
    print("=== TEST 1: 1 000 000 Kč za 20 let, 7 % p.a., měsíční investice ===")
    lump = LumpSumInput(
        target_amount=1_000_000,
        years=20,
        annual_rate_accum=0.07,
        investment_type=InvestmentType.MONTHLY,
    )
    res1 = compute_lump_sum(lump)
    print("Očekávám měsíční investici cca 1 970 Kč")
    print("Výsledek kalkulačky:", pretty(res1["monthly_investment"]))

    print("\n=== TEST 2: 5 000 000 Kč za 18 let (216 měsíců), 7 % p.a., měsíčně ===")
    lump2 = LumpSumInput(
        target_amount=5_000_000,
        years=18,
        annual_rate_accum=0.07,
        investment_type=InvestmentType.MONTHLY,
    )
    res2 = compute_lump_sum(lump2)
    print("Očekávám měsíční investici cca 11 879 Kč")
    print("Výsledek kalkulačky:", pretty(res2["monthly_investment"]))

    print("\n=== TEST 3: Renta 30 000 Kč, 30 let, 5 % p.a. v čerpání ===")
    renta1 = RentaInput(
        monthly_rent=30_000,
        years_rent=30,
        annual_rate_rent=0.05,
        years_saving=18,            # pro ukázku i akumulace
        annual_rate_accum=0.07,
        investment_type=InvestmentType.MONTHLY,
    )
    res3 = compute_renta(renta1)
    print("Očekávám potřebný majetek cca 5 659 788 Kč")
    print("Výsledek kalkulačky:", pretty(res3["required_wealth_at_rent_start"]))

    print("\n=== TEST 4: Renta – majetek 3 372 015 Kč, 18 let, 8 % p.a. (měsíční investice) ===")
    # Tady používáme takovou kombinaci vstupů, aby potřebný majetek vycházel kolem 3 372 015 Kč
    renta2 = RentaInput(
        monthly_rent=17_874,
        years_rent=30,
        annual_rate_rent=0.05,
        years_saving=18,
        annual_rate_accum=0.08,
        investment_type=InvestmentType.MONTHLY,
    )
    res4 = compute_renta(renta2)
    print("Očekávám měsíční investici cca 7 241 Kč")
    print("Výsledek kalkulačky:", pretty(res4["monthly_investment"]))


# ==========================
# Hlavní vstup
# ==========================

if __name__ == "__main__":
    # Na startu se zeptáme, jestli chceš testy nebo ruční zadávání
    mode = ask_choice(
        "\nZvolte režim:",
        {
            "1": "Spustit ukázkové TESTY (ověření, že kalkulačka počítá správně)",
            "2": "Zadat VLASTNÍ HODNOTY v konzoli",
        },
    )
    if mode == "1":
        run_manual_tests()
    else:
        interactive_cli()
