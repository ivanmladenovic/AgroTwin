from unittest import TestCase

from app.knowledge.chunking import chunk_structured_pages
from app.knowledge.structure import StructuredPage
from app.ai.prompts import format_support_block
from app.knowledge.taxonomy import (
    build_retrieval_queries,
    classify_query,
    clip_chat_text,
    expand_query_terms,
    extract_pending_offer,
    fold,
    is_short_affirmative,
    match_manual,
    needs_deep_farm_context,
    needs_soil_lab_context,
)


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
        self.assertEqual(route.answer_mode, "manual_fact")

    def test_commercial_price(self) -> None:
        route = classify_query("Koja je cena proizvoda X?")
        self.assertTrue(route.commercial)
        self.assertEqual(route.answer_mode, "manual_fact")

    def test_seedling_catchup_uses_advice_mode(self) -> None:
        route = classify_query(
            "Da li će male sadnice prestići veće, ili kako da ih pomognem da se izjednače?"
        )
        self.assertEqual(route.answer_mode, "advice")
        queries = build_retrieval_queries(route.question, route)
        self.assertGreaterEqual(len(queries), 2)
        self.assertTrue(any("rast" in fold(item) or "ishran" in fold(item) for item in queries[1:]))
        self.assertFalse(
            needs_deep_farm_context(
                "Imam nekoliko redova gde su mi male sadnice, kada ce one prestici ostatak zasada?"
            )
        )

    def test_irrigation_plan_needs_deep_farm_context(self) -> None:
        self.assertTrue(
            needs_deep_farm_context(
                "Kako preporucujes da navodnjavam naredne godine? Pogledaj moju parcelu i daj mi savet."
            )
        )

    def test_soil_lab_pdf_question_needs_soil_context(self) -> None:
        self.assertTrue(
            needs_soil_lab_context("ubacio sam pdf sa analizom zemljista, daj mi svoje misljenje")
        )
        self.assertTrue(needs_deep_farm_context("ubacio sam pdf sa analizom zemljista, daj mi svoje misljenje"))

    def test_short_affirmative_and_pending_offer(self) -> None:
        self.assertTrue(is_short_affirmative("hajde"))
        self.assertTrue(is_short_affirmative("Da!"))
        self.assertFalse(is_short_affirmative("hajde da izracunamo nesto drugo veoma dugo"))
        offer = extract_pending_offer(
            "Zemljište je dobro.\n\nDa li želite da vam pomognem da izračunamo okvirnu količinu đubriva?"
        )
        self.assertIsNotNone(offer)
        assert offer is not None
        self.assertIn("izracunamo", fold(offer))

    def test_clip_keeps_closing_question(self) -> None:
        body = ("A" * 1400) + "\n\nDa li želite da izračunamo količinu đubriva?"
        clipped = clip_chat_text(body, limit=800)
        self.assertIn("izračunamo", clipped)
        self.assertIn("…", clipped)

    def test_uhvacena_is_not_commercial(self) -> None:
        route = classify_query("Simptomi: uhvacena buba na lešniku")
        self.assertFalse(route.commercial)
        self.assertEqual(route.answer_mode, "advice")
        self.assertIn("protection", route.document_keys)

    def test_field_report_stays_advice(self) -> None:
        route = classify_query(
            "Prijavljen je problem: Buba. Simptomi: uhvacena buba. Pregledajte opažanje."
        )
        self.assertFalse(route.commercial)
        self.assertEqual(route.answer_mode, "advice")

    def test_dose_question_uses_manual_fact(self) -> None:
        route = classify_query("Koja je doza bora po hektaru?")
        self.assertEqual(route.answer_mode, "manual_fact")

    def test_fungicide_name_uses_manual_fact(self) -> None:
        route = classify_query("Koji fungicid koristiti protiv monilioze?")
        self.assertEqual(route.answer_mode, "manual_fact")

    def test_support_block_allows_empty_sources(self) -> None:
        block = format_support_block([])
        self.assertIn("SUPPORTING MANUAL EXCERPTS", block)
        self.assertIn("none", block)

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
