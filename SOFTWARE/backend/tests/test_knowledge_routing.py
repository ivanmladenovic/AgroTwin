from unittest import TestCase

from app.knowledge.chunking import chunk_structured_pages
from app.knowledge.structure import StructuredPage
from app.knowledge.taxonomy import classify_query, expand_query_terms, fold, match_manual


class RoutingTests(TestCase):
    def test_potassium_symptoms_route_to_nutrition_macro(self) -> None:
        route = classify_query("Koji su simptomi nedostatka kalijuma?")
        self.assertIn("nutrition", route.document_keys)
        self.assertTrue(any(item in route.topics for item in ("macroelements", "microelements")) or "nutrition" in route.domains)

    def test_boron_routes_to_microelements(self) -> None:
        route = classify_query("Koji su simptomi nedostatka bora?")
        self.assertIn("nutrition", route.document_keys)
        self.assertIn("microelements", route.topics)

    def test_preplant_fertilization(self) -> None:
        route = classify_query("Kako se vrši đubrenje pre sadnje?")
        self.assertTrue("nutrition" in route.document_keys or "cultivation" in route.document_keys)

    def test_soil_preparation(self) -> None:
        route = classify_query("Kako pripremiti zemljište pre podizanja zasada?")
        self.assertIn("cultivation", route.document_keys)

    def test_spacing(self) -> None:
        route = classify_query("Koje rastojanje treba koristiti pri sadnji?")
        self.assertIn("cultivation", route.document_keys)
        self.assertIn("spacing", route.topics)

    def test_pruning(self) -> None:
        route = classify_query("Kako se vrši rezidba leske?")
        self.assertIn("cultivation", route.document_keys)
        self.assertIn("pruning", route.topics)

    def test_irrigation(self) -> None:
        route = classify_query("Kako navodnjavati lesku?")
        self.assertIn("cultivation", route.document_keys)
        self.assertIn("irrigation", route.topics)

    def test_fungal_diseases(self) -> None:
        route = classify_query("Koje gljivične bolesti napadaju lesku?")
        self.assertIn("protection", route.document_keys)
        self.assertIn("fungal_diseases", route.topics)

    def test_frost(self) -> None:
        route = classify_query("Kako prepoznati štetu od mraza?")
        self.assertIn("protection", route.document_keys)
        self.assertIn("frost", route.topics)

    def test_young_tree_calendar(self) -> None:
        route = classify_query("Koji je kalendar zaštite za mlada stabla?")
        self.assertIn("protection", route.document_keys)
        self.assertIn("young_trees", route.topics)

    def test_cross_document_health(self) -> None:
        route = classify_query("Kako ishrana utiče na zdravlje i otpornost leske?")
        self.assertIn("nutrition", route.document_keys)
        self.assertIn("protection", route.document_keys)

    def test_out_of_scope_capital(self) -> None:
        route = classify_query("Koji je glavni grad Francuske?")
        self.assertTrue(route.out_of_scope)

    def test_commercial_price(self) -> None:
        route = classify_query("Koja je cena proizvoda X?")
        self.assertTrue(route.commercial)

    def test_synonyms_expand_fertilization(self) -> None:
        terms = expand_query_terms("gnojidba leske")
        self.assertTrue(any("dju" in item or "gnoj" in item for item in terms))

    def test_manual_filename_match(self) -> None:
        spec = match_manual("Prirucnik - Ishrana leske.pdf", "Ishrana")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.domain, "nutrition")


class ChunkingTests(TestCase):
    def test_short_section_stays_together(self) -> None:
        pages = [
            StructuredPage(
                page_number=3,
                raw_text="Uloga kalijuma kod leske je važna.",
                normalized_text="Uloga kalijuma kod leske je važna za otpornost.",
                chapter="Osnovna hraniva",
                section="Makroelementi",
                subsection=None,
                domain="nutrition",
                topic="macroelements",
                headings=["Makroelementi"],
                has_text_layer=True,
                ocr_used=False,
                image_png=None,
                embedded_images=[],
            )
        ]
        chunks = chunk_structured_pages(pages, "Priručnik - Ishrana leske")
        text_chunks = [item for item in chunks if item["content_type"] == "text"]
        self.assertEqual(len(text_chunks), 1)
        self.assertEqual(text_chunks[0]["section_title"], "Makroelementi")
        self.assertIn("kalijuma", text_chunks[0]["content"])

    def test_heading_does_not_match_incidental_investicije(self) -> None:
        from app.knowledge.structure import _heading_matches
        import re

        text = "Poznavanje svojstva zemljišta date oblasti je od presudne važnosti. Od toga zavisi uspeh ili neuspeh investicije."
        folded = fold(text)
        compact = re.sub(r"[^a-z0-9]+", "", folded)
        self.assertFalse(_heading_matches("Dodatne investicije pri podizanju zasada", folded, compact))
        self.assertEqual(fold("Đubrenje"), "djubrenje")
        self.assertNotEqual("Đubrenje", fold("Đubrenje"))
