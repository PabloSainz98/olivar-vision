import unittest

from olivar_vision.status import extract_section, parse_status


class StatusParsingTests(unittest.TestCase):
    def test_parse_status_reads_live_fields_and_next_action_section(self):
        readme = """# Demo

## Estado vivo

- Estado documentado: VALIDADA.
- Fase activa: 1 - inventario.
- Extension LiDAR-carbono: L1 EN CURSO.
- Ultimo hito completado: fase 0.
- Comprobaciones realizadas: make check OK.
- Siguiente accion: texto antiguo.

## Siguiente accion

Iniciar fase 1 sin descargar datos.
"""
        status = parse_status(readme)

        self.assertEqual(status.get("Estado documentado"), "VALIDADA.")
        self.assertEqual(status.get("Fase activa"), "1 - inventario.")
        self.assertEqual(status.get("Extension LiDAR-carbono"), "L1 EN CURSO.")
        self.assertEqual(status.get("Ultimo hito completado"), "fase 0.")
        self.assertEqual(status.get("Comprobaciones realizadas"), "make check OK.")
        self.assertEqual(
            status.get("Siguiente accion"),
            "Iniciar fase 1 sin descargar datos.",
        )

    def test_extract_section_stops_at_next_heading(self):
        lines = [
            "# Title",
            "intro",
            "## Estado vivo",
            "- one",
            "## Registro de fases",
            "- two",
        ]

        self.assertEqual(extract_section(lines, "Estado vivo"), ["- one"])


if __name__ == "__main__":
    unittest.main()
