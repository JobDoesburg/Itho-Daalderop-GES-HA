# Itho Daalderop Home Assistant Integration

<p align="center">
  <img src="icon.svg" width="200" alt="Itho Daalderop Integration Icon"/>
</p>

<p align="center">
  <a href="https://github.com/custom-components/hacs"><img src="https://img.shields.io/badge/HACS-Custom-orange.svg" alt="HACS"></a>
  <a href="https://github.com/marinuz/Itho-Daalderop-GES-HA/releases"><img src="https://img.shields.io/github/release/marinuz/Itho-Daalderop-GES-HA.svg" alt="GitHub Release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/marinuz/Itho-Daalderop-GES-HA.svg" alt="License"></a>
</p>

Professionele Home Assistant integratie voor Itho Daalderop boiler met Cloud Connect functionaliteit.

## 🏷️ Ondersteunde apparaten

De integratie herkent het boilertype aan de eerste drie letters van het serienummer:

| Serienummer | Type | Ondersteuning |
|---|---|---|
| `VPR...` | Green Energy Smartboiler® | Volledig: alle modi, temperatuurinstelling, PV-functie |
| `GRB...` | Smartboiler (met Smart-upp module) | Modi SmartControl/Schedule/Holiday, Boost, monitoring. Geen PV-functie of vrije temperatuurinstelling (de boiler regelt dit zelflerend; Boost verwarmt eenmalig naar 85°C) |

**Bekende beperking (alle typen):** de Boost-knop werkt momenteel niet.
De API weigert de aanroep (`BoostBoilerRequestContract` validatiefout) — het
verwachte request-formaat is nog onbekend. Wie het netwerkverkeer van de
Climate Connect app kan opvangen (mitmproxy) kan dit oplossen; zie issue #1.

**Let op:** modus-wijzigingen zijn *eventually consistent*: de API bevestigt
direct, maar `GetDeviceMode` geeft tot ~30 seconden de oude modus terug.
De integratie werkt hier omheen met een optimistische update.

Onbekende serienummers krijgen het volledige (VPR) profiel. Werkt iets niet
op jouw boilertype? Download dan de diagnostics (Instellingen → Apparaten &
diensten → Itho Daalderop → Diagnostics downloaden) of draai
`tests/probe_device.py` en open een issue met de output — daarmee kan het
profiel voor jouw type verfijnd worden.

## ✨ Features

### 🎛️ **Volledige Controle**
- ✅ **Water Heater Entity** voor complete boiler besturing
- ✅ **Temperatuur regeling** (10-75°C) met real-time feedback
- ✅ **4 Bedrijfsmodi**: SmartControl, Schedule, Continuous, Holiday
- ✅ **Boost functie** met status indicator (schakelaar)

### ☀️ **PV (Zonnepanelen) Optimalisatie**
- ✅ **PV Functie aan/uit** schakelbaar
- ✅ **Instelbare start/stop limieten** voor PV overschot (kW)
- ✅ **PV doeltemperatuur** configureerbaar (°C)
- ✅ **Live PV monitoring**: verbruik, productie en netto vermogen

### 📊 **Uitgebreide Monitoring** (16+ sensors)
- ✅ Boiler inhoud percentage
- ✅ Water temperatuur live
- ✅ Stroomverbruik actueel (W)
- ✅ Energie verbruik totaal (kWh)
- ✅ Energie besparing (kWh)
- ✅ Legionella preventie timer
- ✅ Software versie
- ✅ Online/Offline status

### 🔒 **Betrouwbaar & Veilig**
- ✅ **Token-based authenticatie** (geen wachtwoord in HA)
- ✅ **1-jaar geldigheid** met automatische refresh
- ✅ **Retry logic** voor netwerkfouten
- ✅ **Rate limiting** om API te beschermen
- ✅ **HACS compatible**  

## Installatie via HACS

Zie de [volledige installatie gids](docs/HACS_INSTALL_GUIDE.md) voor gedetailleerde instructies.

### Quick Start

#### Optie 1: Custom Repository (Aanbevolen voor testing)

1. Open **HACS** in Home Assistant
2. Klik op **Integrations**
3. Klik rechtsbovenin op de **︙** (drie puntjes)
4. Selecteer **Custom repositories**
5. Voeg toe:
   - **Repository**: `https://github.com/marinuz/Itho-Daalderop-GES-HA.git`
   - **Category**: `Integration`
6. Klik op **Add**
7. Zoek naar "Itho Daalderop" en klik op **Download**
8. Herstart Home Assistant

### Optie 2: Handmatige installatie

1. Download deze repository
2. Kopieer de `custom_components/itho_daalderop` folder naar je Home Assistant `custom_components` directory
3. Herstart Home Assistant

## Configuratie

1. Ga naar **Instellingen** → **Apparaten & Services**
2. Klik op **+ Integratie toevoegen**
3. Zoek naar **Itho Daalderop**
4. Voer het **serienummer** van je boiler in (bijv. `VPR242600095`)
5. Er opent een browser naar de Itho login pagina
6. Log in met je **Itho Daalderop account**
7. Na inloggen krijg je een foutmelding - dit is normaal!
8. Open **Browser Console** (F12)
9. Kopieer de URL die begint met `climateconnect://login?token=...`
10. Plak deze in Home Assistant
11. Klaar! Je boiler is nu beschikbaar in HA

## Entiteiten

### 🌡️ Water Heater
**Hoofdentiteit voor boiler besturing**
- **Temperatuur**: 10-75°C instelbaar
- **Modi**: 
  - `Eco` (SmartControl) - Slimme automatische modus
  - `Auto` (Schedule) - Volgens weekschema
  - `Heat Pump` (Continuous) - Altijd aan
  - `Off` (Holiday) - Vakantie modus
- **Attributen**: Alle sensor data beschikbaar

### 🔘 Switches (2)
- **Boost Mode** 🚀
  - Activeer snelle opwarming
  - Status feedback (aan/uit)
  
- **PV Function** ☀️
  - Schakel PV-overschot verwarming aan/uit
  - Real-time status

### Water Heater Services (Home Assistant standaard)
```yaml
# Stel temperatuur in
service: water_heater.set_temperature
target:
  entity_id: water_heater.itho_boiler_vpr242600095
data:
  temperature: 60

# Wijzig bedrijfsmodus
service: water_heater.set_operation_mode
target:
  entity_id: water_heater.itho_boiler_vpr242600095
data:
  operation_mode: "eco"  # eco, auto, heat_pump, off
```

### Custom Services
```yaml
# Activeer boost mode
service: itho_daalderop.boost_boiler
data:
  activate: true
```

## Automatisering Voorbeelden

### PV Overschot Optimalisatie
```yaml
automation:
  - alias: "Boiler: Warm water bij zonne-overschot"
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
          value: 75  # Maximaal opwarmen
```

### Boost bij lage boiler inhoud
```yaml
automation:
  - alias: "Boiler: Boost bij laag niveau"
    trigger:
      - platform: numeric_state
        entity_id: sensor.boiler_content
        below: 20  # Onder 20%
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.boost_mode
```

### Nacht tarief optimalisatie
```yaml
automation:
  - alias: "Boiler: Opwarmen tijdens nacht tarief"
    trigger:
      - platform: time
        at: "23:00:00"
    action:
      - service: water_heater.set_temperature
        target:
          entity_id: water_heater.itho_boiler
        data:
          temperature: 75
      - service: water_heater.set_operation_mode
        target:
          entity_id: water_heater.itho_boiler
        data:
          operation_mode: "heat_pump"
```
  
- **PV Stop Limit** (0-10 kW, stap 0.1)
  - Stop boiler onder deze limiet
  
- **PV Target Temperature** (40-90°C, stap 1)
  - Doeltemperatuur voor PV-modus

### 📊 Sensors (16)
**Device Status**
- `Boiler Content` - Vulgraad (%)
- `Device State` - Online/Offline status
- `Device Mode` - Huidige bedrijfsmodus
- `Device Power` - Actueel vermogen (W)
- `Water Temperature` - Huidige temp (°C)
- `Software Version` - Firmware versie
- `Legionella Timer` - Tijd tot preventie (uur)

**Energy Monitoring**
- `Energy Consumption` - Totaal verbruik (kWh)
- `Energy Saving` - Totale besparing (kWh)

**PV Monitoring**
- `PV Net Power` - Netto vermogen (kW, - = teruglevering)
- `PV Power Consumption` - Afname van net (kW)
- `PV Power Production` - Levering aan net (kW)

**PV Settings (read-only sensors)**
- `PV Enabled` - Status (On/Off)
- `PV Start Limit` - Huidige startwaarde (kW)
- `PV Stop Limit` - Huidige stopwaarde (kW)

## Services

De integratie biedt een Water Heater entity met standaard Home Assistant services:

- `water_heater.set_temperature` - Stel doeltemperatuur in
- `water_heater.set_operation_mode` - Wijzig bedrijfsmodus

## Troubleshooting

### Kan geen login URL kopiëren?
- Open Browser Console met **F12** of **Ctrl+Shift+I**
- Zoek naar de regel met "Failed to launch"
- De URL staat ook vaak in de **adresbalk** van de browser

### Token werkt niet?
- Zorg dat je de **volledige URL** kopieert, inclusief `climateconnect://login?token=`
- Token is 1 jaar geldig, daarna opnieuw inloggen

### Boiler reageert niet?
- Controleer of het serienummer correct is (hoofdletters!)
- Controleer of de boiler online is in de Itho app

## Licentie

MIT License - zie [LICENSE](LICENSE) voor details.

## Bijdragen

Bijdragen zijn welkom! Zie [CONTRIBUTING.md](CONTRIBUTING.md) voor richtlijnen.

## Support

- 📚 [Documentatie](docs/)
- 🐛 [Issues](https://github.com/yourusername/itho-daalderop-ha/issues)
- 💬 [Discussions](https://github.com/yourusername/itho-daalderop-ha/discussions)

## Credits

Ontwikkeld door de Home Assistant community.  
Gebaseerd op de Itho Daalderop Cloud Connect API.
