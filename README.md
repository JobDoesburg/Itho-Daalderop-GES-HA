# Itho Daalderop Home Assistant Integration

<p align="center">
  <img src="icon.svg" width="200" alt="Itho Daalderop Integration Icon"/>
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/JobDoesburg/Itho-Daalderop-GES-HA.svg" alt="License"></a>
</p>

Home Assistant integratie voor Itho Daalderop boilers die via de Climate
Connect app (Cloud Connect API) worden bediend.

## 🏷️ Ondersteunde apparaten

De integratie herkent het boilertype aan de eerste drie letters van het serienummer:

| Serienummer | Type | Ondersteuning |
|---|---|---|
| `VPR...` | Green Energy Smartboiler® | Volledig: 4 modi, temperatuurinstelling, PV-functie |
| `GRB...` | Smartboiler (met Smart-upp module) | 4 modi en monitoring. Geen PV-functie; doeltemperatuur is alleen-lezen (de API accepteert een wijziging maar negeert deze — live geverifieerd) |

Onbekende serienummers krijgen het volledige (VPR) profiel. Werkt iets niet
op jouw boilertype? Download dan de diagnostics (Instellingen → Apparaten &
diensten → Itho Daalderop → Diagnostics downloaden) of draai
`tests/probe_device.py` en open een
[issue](https://github.com/JobDoesburg/Itho-Daalderop-GES-HA/issues) met de
output — daarmee kan het profiel voor jouw type verfijnd worden.

### Bekende beperkingen

- **Boost werkt momenteel niet** (alle typen): de API weigert de aanroep
  (`BoostBoilerRequestContract` validatiefout) — het verwachte
  request-formaat is nog onbekend. Wie het netwerkverkeer van de Climate
  Connect app kan opvangen (bijv. met mitmproxy) kan dit oplossen.
- **Modus-wijzigingen zijn *eventually consistent***: de API bevestigt
  direct, maar geeft tot ~30 seconden de oude modus terug. De integratie
  werkt hier omheen met een optimistische update; de boiler zelf volgt
  binnen ~30 seconden.

## ✨ Features

- **Bedrijfsmodus** instelbaar via één select entity met dezelfde namen
  als de app: Smart, Schedule, Always on, Standby
- **Temperatuurinstelling** (10–75°C, alleen VPR)
- **PV (zonnepanelen) optimalisatie** (alleen VPR): PV-functie aan/uit,
  start/stop limieten, PV doeltemperatuur, live PV monitoring
- **Uitgebreide monitoring**: vulgraad, vermogen, energieverbruik en
  -kosten van vandaag, besparing, doeltemperatuur, boost status,
  legionella preventie timer, online/offline status, firmware versie
- **Token-based authenticatie** (geen wachtwoord in HA); token is 1 jaar
  geldig, daarna opnieuw inloggen
- **Diagnostics ondersteuning** voor het debuggen van nieuwe boilertypes
- **HACS compatible**

## Installatie

### Optie 1: via HACS (aanbevolen)

1. Open **HACS** in Home Assistant
2. Klik rechtsbovenin op de **︙** (drie puntjes) → **Custom repositories**
3. Voeg toe:
   - **Repository**: `https://github.com/JobDoesburg/Itho-Daalderop-GES-HA`
   - **Category**: `Integration`
4. Zoek naar "Itho Daalderop" en klik op **Download**
5. Herstart Home Assistant

### Optie 2: handmatig

1. Download deze repository
2. Kopieer de map `custom_components/itho_daalderop` naar de
   `custom_components` directory van je Home Assistant configuratie
3. Herstart Home Assistant

## Configuratie

1. Ga naar **Instellingen** → **Apparaten & Services**
2. Klik op **+ Integratie toevoegen** en zoek naar **Itho Daalderop**
3. Voer het **serienummer** van je boiler in (bijv. `VPR242600095` of
   `GRB240230157`)
4. Klik op de login-link en log in met je **Itho Daalderop account**
5. Na inloggen probeert de browser `climateconnect://login?token=...` te
   openen en toont een foutmelding — dit is normaal!
6. Kopieer uit de adresbalk (of browser console, F12) de token: alles na
   `token=`, beginnend met `eyJ` en met precies twee punten erin
7. Plak deze in Home Assistant — klaar!

## Entiteiten

### 🎚️ Select
- **Device Mode** — bedrijfsmodus, met dezelfde namen als de app
  (API-waarde tussen haakjes):
  - `Smart` (SmartControl) — slimme zelflerende modus
  - `Schedule` (Schedule) — volgens weekschema
  - `Always on` (Continuous) — altijd aan
  - `Standby` (Holiday) — uit; in de app heet dit "standby", de
    vakantiemodus van de app is standby met een begin- en einddatum

### 🔘 Switches
- **PV Function** — PV-overschot verwarming aan/uit *(alleen VPR)*

### 🔔 Binary sensors
- **Boost Active** — of boost actief is *(alleen-lezen: boost aanzetten
  kan nog niet, zie beperkingen)*

### 🔢 Numbers *(alleen VPR)*
- **Temperatuur Instelling** (10–75°C)
- **PV Start Limit** (0–10 kW) — start boiler boven dit PV-overschot
- **PV Stop Limit** (0–10 kW) — stop boiler onder deze limiet
- **PV Target Temperature** (40–90°C) — doeltemperatuur voor PV-modus

### 📊 Sensors

**Alle typen**
- `Boiler Content` — vulgraad (%)
- `Device State` — Online/Offline
- `Device Power` — actueel vermogen (kW)
- `Target Temperature` — ingestelde doeltemperatuur (°C)
- `Energy Consumption Today` — verbruik vandaag (kWh, zoals in de app)
- `Energy Costs Today` — kosten vandaag (EUR)
- `Energy Saving` — besparing (kWh)
- `Legionella Prevention Timer` — tijd tot preventie (uur)
- `Software Version` — firmware versie

**Alleen VPR**
- `Water Temperature` — gemeten watertemperatuur (°C)
- `PV Net Power`, `PV Power Consumption`, `PV Power Production` (kW)
- `PV Enabled`, `PV Start Limit`, `PV Stop Limit`

## Services

```yaml
# Activeer boost mode (werkt nog niet, zie beperkingen)
service: itho_daalderop.boost_boiler
data:
  activate: true

# Stel een weekschema in
service: itho_daalderop.set_schedule
data:
  schedule:
    "0": { "7": 60, "22": 40 }  # maandag: 07:00 60°C, 22:00 40°C
```

## Automatisering voorbeelden

### Standby bij afwezigheid
```yaml
automation:
  - alias: "Boiler: standby bij afwezigheid"
    trigger:
      - platform: state
        entity_id: group.familie
        to: "not_home"
        for: "24:00:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.device_mode
        data:
          option: "Standby"
```

### PV overschot optimalisatie (alleen VPR)
```yaml
automation:
  - alias: "Boiler: warm water bij zonne-overschot"
    trigger:
      - platform: numeric_state
        entity_id: sensor.solar_power_surplus
        above: 2.0  # 2 kW overschot
    condition:
      - condition: state
        entity_id: switch.pv_function
        state: "on"
    action:
      - service: number.set_value
        target:
          entity_id: number.pv_target_temperature
        data:
          value: 75
```

### Melding bij lage boilerinhoud
```yaml
automation:
  - alias: "Boiler: melding bij laag niveau"
    trigger:
      - platform: numeric_state
        entity_id: sensor.boiler_content
        below: 20  # onder 20%
    action:
      - service: notify.mobile_app
        data:
          message: "Boiler bijna leeg ({{ states('sensor.boiler_content') }}%)"
```

## Troubleshooting

### Token werkt niet?
- De juiste token begint met `eyJ` en bevat **precies twee punten** (drie
  delen). Een token met vier punten is een tussenproduct van de Azure
  login en werkt niet.
- Token is 1 jaar geldig. Daarna: verwijder de integratie en voeg deze
  opnieuw toe met een verse token.

### Modus verandert niet direct?
- De boiler volgt een moduswijziging binnen ~30 seconden; de API geeft in
  die periode nog de oude modus terug. Dit is normaal.

### Entiteiten "niet beschikbaar" na update?
- Sommige entiteiten zijn vervangen of worden per boilertype niet meer
  aangemaakt (de Boost- en Vakantie-schakelaars zijn vervangen door de
  Device Mode select en de Boost Active binary sensor; op GRB vervallen
  ook de PV- en temperatuurentiteiten). Verwijder de oude entiteiten uit
  het entiteitenregister, of verwijder de integratie en voeg deze opnieuw
  toe.

### Boiler reageert niet?
- Controleer of het serienummer correct is (hoofdletters!)
- Controleer of de boiler online is in de Climate Connect app

## Licentie

MIT License — zie [LICENSE](LICENSE) voor details.

## Bijdragen

Bijdragen zijn welkom! Zie [CONTRIBUTING.md](CONTRIBUTING.md) voor
richtlijnen. Vooral gezocht: het request-formaat van de Boost-functie
(netwerkverkeer van de Climate Connect app).

## Support

- 📚 [Documentatie](docs/)
- 🐛 [Issues](https://github.com/JobDoesburg/Itho-Daalderop-GES-HA/issues)

## Credits

Gebaseerd op [Rien-R/Itho-Daalderop-GES-HA](https://github.com/Rien-R/Itho-Daalderop-GES-HA)
en de Itho Daalderop Cloud Connect API. GRB-ondersteuning getest op een
Smartboiler GRB240230157.
