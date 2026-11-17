from __future__ import annotations

from pydantic import BaseModel, Field

from aliexpress_deals.arbitrage import CustomsMode


class EquipmentPreset(BaseModel):
    slug: str
    name_uk: str
    search_keywords: list[str]
    recommended_countries: list[str] = Field(default_factory=lambda: ["UA"])
    estimated_weight_kg: float = 0.5
    customs_mode: CustomsMode = CustomsMode.STANDARD_150EUR
    min_rating: float = 4.5
    notes_uk: str = ""


EQUIPMENT_PRESETS: dict[str, EquipmentPreset] = {
    "power_station_2kwh": EquipmentPreset(
        slug="power_station_2kwh",
        name_uk="Зарядна станція 2 кВт·год+, 2 кВт+ (LiFePO4)",
        search_keywords=[
            "2000W 2000Wh LiFePO4 portable power station",
            "Fossibot F2400 2048Wh 2400W",
            "Oukitel P2001 Plus 2048Wh 2400W",
            "Allpowers R2500 2016Wh 2500W",
        ],
        recommended_countries=["PL", "DE", "UA"],
        estimated_weight_kg=22.5,
        customs_mode=CustomsMode.ENERGY_EXEMPT,
        min_rating=4.6,
        notes_uk=(
            "Найвигідніше замовляти зі складів ЄС (PL/DE) з безкоштовною доставкою по ЄС "
            "на склад Meest Poland / NP Shopping, оскільки пряма доставка батарей у UA часто закрита."
        ),
    ),
    "hydraulic_crimper": EquipmentPreset(
        slug="hydraulic_crimper",
        name_uk="Гідравлічний обтискач для наконечників",
        search_keywords=[
            "hydraulic crimping tool YQK-70 4-70mm2",
            "hydraulic cable lug crimper YQK-120",
            "hydraulic crimper YQK-300 battery terminal",
        ],
        recommended_countries=["UA", "PL"],
        estimated_weight_kg=2.8,
        customs_mode=CustomsMode.STANDARD_150EUR,
        min_rating=4.6,
        notes_uk="Звертати увагу на діапазон матриць у комплекті (4–70 мм² або 10–120 мм²) та профіль обтиску (шестигранний).",
    ),
    "battery_charger": EquipmentPreset(
        slug="battery_charger",
        name_uk="Зарядний пристрій для акумуляторів (LiFePO4 / Лабораторний БЖ)",
        search_keywords=[
            "LiFePO4 battery charger 14.6V 20A",
            "LiFePO4 charger 12V 24V 30A smart charger",
            "Wanptek lab power supply 30V 10A",
            "HTRC smart battery charger LiFePO4",
        ],
        recommended_countries=["UA", "PL"],
        estimated_weight_kg=1.2,
        customs_mode=CustomsMode.STANDARD_150EUR,
        min_rating=4.7,
        notes_uk="Для LiFePO4 критично мати профіль CC/CV 14.6V (для 4S 12V) або 29.2V (для 8S 24V).",
    ),
    "battery_load_tester": EquipmentPreset(
        slug="battery_load_tester",
        name_uk="Розрядка-навантаження для тесту ємності акумуляторів",
        search_keywords=[
            "Atorch DL24 150W electronic load battery capacity tester",
            "DL24P 180W USB electronic load discharge tester",
            "DL24MP 150W four wire battery tester",
        ],
        recommended_countries=["UA"],
        estimated_weight_kg=0.45,
        customs_mode=CustomsMode.STANDARD_150EUR,
        min_rating=4.8,
        notes_uk="Обирати версію з 4-провідним (Kelvin) підключенням для точного вимірювання без просідання на дротах.",
    ),
    "soldering_iron": EquipmentPreset(
        slug="soldering_iron",
        name_uk="Паяльник (USB-C PD / індукційний / станція T12)",
        search_keywords=[
            "FNIRSI HS-02 USB PD 100W soldering iron",
            "TS101 smart soldering iron",
            "Pinecil V2 soldering iron",
            "Quecoo T12 956 soldering station",
        ],
        recommended_countries=["UA"],
        estimated_weight_kg=0.35,
        customs_mode=CustomsMode.STANDARD_150EUR,
        min_rating=4.8,
        notes_uk="Для силових клем акумуляторів бажано брати жало типу K або C4 та потужність 65W–100W PD.",
    ),
    "welder": EquipmentPreset(
        slug="welder",
        name_uk="Зварювальний апарат (інверторний / точкове зварювання АКБ)",
        search_keywords=[
            "AWithZ battery spot welder 18650 LiFePO4",
            "Docreate capacitor spot welder",
            "IGBT inverter welding machine MMA MIG",
        ],
        recommended_countries=["UA", "PL"],
        estimated_weight_kg=3.5,
        customs_mode=CustomsMode.STANDARD_150EUR,
        min_rating=4.6,
        notes_uk="Розрізняти точкове зварювання нікелевої/мідної стрічки для АКБ та класичний інвертор MMA/MIG.",
    ),
    "multimeter": EquipmentPreset(
        slug="multimeter",
        name_uk="Мультиметр цифровий True RMS",
        search_keywords=[
            "ZOYI ZT-S1 digital multimeter True RMS",
            "FNIRSI DMT-99 10000 counts multimeter",
            "ANENG AN8008 True RMS multimeter",
            "UNI-T UT61E+ digital multimeter",
        ],
        recommended_countries=["UA"],
        estimated_weight_kg=0.35,
        customs_mode=CustomsMode.STANDARD_150EUR,
        min_rating=4.8,
        notes_uk="Для роботи з інверторами та АКБ обов'язково True RMS; корисно також мати струмові кліщі DC (наприклад UNI-T UT210E).",
    ),
}
