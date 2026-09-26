# Analytics und Pin-Auswertung

## Einrichtung

- GA4-Property: Leo Bergmann – Autorenwebsite (555941179)
- Webstream: Leo Bergmann Website (15849179388)
- Mess-ID: G-9YTBES6ERF (öffentliche Konfiguration, kein Geheimnis)
- Verwaltung: https://analytics.google.com/analytics/web/#/a409522839p555941179/
- `amazon_click` ist ein Schlüsselereignis ohne zugewiesenen Geldwert.
- Ereignisdimensionen: Buch (`book_id`), Pin Variante (`pin_variant`), Klickposition (`cta_position`).

## Was gemessen wird

Nach Zustimmung: Seitenbesuche, Herkunft, Interaktionen und Klicks von den Rezeptseiten zu Amazon. Amazon-Klicks sind keine Käufe. Verkäufe und Umsatz auf Amazon werden durch diese Integration nicht erfasst.

Neue Feed-Links enthalten `utm_source=pinterest`, `utm_medium=organic`, `utm_campaign=<book_id>` und bei bekannten neuen Designs `utm_content=<catalog_id>:<variant>`. GUIDs und kanonische Seiten-URLs bleiben stabil. Bereits veröffentlichte Pins werden nicht nachträglich einer neuen Gestaltung zugeschrieben. Pinterest kann bestehende Bilddateien zwischenspeichern; die lokalen Bildänderungen ersetzen veröffentlichte Pins nicht automatisch.

## Auswertung

1. In GA4 unter Berichte die Traffic-Akquisition öffnen und nach Quelle/Medium `pinterest / organic` filtern.
2. In der explorativen Datenanalyse die Dimensionen Buch, Pin Variante und Klickposition importieren. Als Messwerte aktive Nutzer, Sitzungen und Ereignisanzahl verwenden.
3. Für Amazon-Klicks nach Ereignisname `amazon_click` filtern. Die Klickposition zeigt `hero`, `book_offer`, `closing` oder `mobile_bar`.
4. Pinterest Analytics separat für Impressionen und ausgehende Klicks nutzen. Die ausgehende Klickrate ist ausgehende Klicks / Impressionen. GA4 kennt die Pinterest-Impressionen nicht.
5. Varianten über vergleichbare Zeiträume, Themen und Reichweiten vergleichen. Die deterministische Verteilung über Rezepte ist kein kontrollierter A/B-Test. Kleine Stichproben und Unterschiede zwischen Rezepten erlauben keine belastbare Aussage zur Wirkung des Designs.

Eine Steigerung der Klickrate ist eine Hypothese, keine Garantie. Ohne historische Vergleichsdaten lässt sich kein seriöser Steigerungsprozentsatz angeben. Neue benutzerdefinierte Dimensionen und Standardberichte können verzögert verfügbar sein.

## Einwilligung

Der Google-Tag wird erst nach ausdrücklicher Zustimmung geladen. Ablehnung verursacht keine Analytics-Anfragen. Die Auswahl wird höchstens 180 Tage lokal gespeichert; Analytics-Cookies werden auf 180 Tage begrenzt. Statistik-Einstellungen im Seitenfuß erlauben den Widerruf. Werbeeinwilligungen bleiben abgelehnt; Google Signals und Werbepersonalisierung sind deaktiviert. Lokale Vorschauen senden keine Daten. Nutzer ohne Einwilligung und Browser mit Blockern fehlen in den Messwerten.

## Wartung

Die Mess-ID steht in `site_config.json`, die Einwilligungs- und Klicklogik in `assets/analytics.js`. `build.py` kopiert die Integration nach `docs/`. Der Scheduler übernimmt die Gestaltungsvariante neuer Einträge. Vorberechnete Designs liegen unter `docs/assets/pins/`.
