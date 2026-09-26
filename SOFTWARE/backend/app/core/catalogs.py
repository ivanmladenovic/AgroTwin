"""Configurable activity types and cost categories.

These are stored in the database so the frontend never hardcodes the lists.
The tuples below are the canonical seed/upsert source.
"""

ACTIVITY_TYPES: list[tuple[str, str, str]] = [
    ("irrigation", "Navodnjavanje", "Voda naneta na parcelu, red ili stablo."),
    ("spraying", "Prskanje", "Zaštita bilja ili folijarno prskanje."),
    ("fertilization", "Đubrenje", "Unošenje hraniva."),
    ("soil_analysis", "Analiza zemljišta", "Laboratorijska analiza uzoraka zemljišta sa parcele."),
    ("pruning", "Rezidba", "Rezidba krošnje ili izdanaka."),
    ("planting", "Sadnja", "Sadnja novih stabala."),
    ("harvesting", "Berba", "Sakupljanje plodova i radovi u berbi."),
    ("maintenance", "Održavanje", "Infrastruktura ili održavanje voćnjaka."),
    ("inspection", "Pregled", "Terenski pregled bez tretmana."),
    ("disease_treatment", "Tretman bolesti", "Tretman zabeleženog zdravstvenog problema."),
    ("tree_removal", "Uklanjanje stabla", "Uklanjanje uginulog ili neproduktivnog stabla."),
    ("tree_replacement", "Zamena stabla", "Zamena uklonjenog stabla."),
    ("other", "Ostalo", "Bilo koja druga aktivnost u voćnjaku."),
]

COST_CATEGORIES: list[tuple[str, str, str]] = [
    ("planting_material", "Sadni materijal", "Sadnice, kalemovi i srodni sadni materijal."),
    ("fertilizers", "Đubriva", "Mineralna i organska đubriva."),
    ("plant_protection", "Zaštita bilja", "Pesticidi, fungicidi i srodna sredstva."),
    ("water", "Voda", "Voda za navodnjavanje."),
    ("electricity", "Struja", "Energija za pumpe, osvetljenje ili opremu."),
    ("fuel", "Gorivo", "Dizel, benzin i druga goriva."),
    ("labor", "Rad", "Plaćeni rad i angažovanje izvođača."),
    ("machinery", "Mašine", "Iznajmljivanje ili rad mašina."),
    ("maintenance", "Održavanje", "Popravka i održavanje imovine voćnjaka."),
    ("equipment", "Oprema", "Alat i nabavka opreme."),
    ("harvesting", "Berba", "Materijal i usluge vezani za berbu."),
    ("transport", "Prevoz", "Transport i prevoz."),
    ("other", "Ostalo", "Nerazvrstani trošak voćnjaka."),
]
