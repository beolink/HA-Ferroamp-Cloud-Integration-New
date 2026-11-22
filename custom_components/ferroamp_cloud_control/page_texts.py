"""What the Ferroamp page says: its headings, its words for states, and an
explanation for every value and every option on it.

Free of Home Assistant imports, like page_views.py, so every text can be
checked without an installation (tests/test_page.py). Every text is written
twice, Swedish and English: the page is built in Home Assistant's language,
Swedish where it is set to Swedish and English otherwise. The texts rest on
what PROTOCOL.md records about the cloud and what was seen on a live ESO 15
facility; where that does not settle what a value means, the text says so
rather than guessing.
"""

from __future__ import annotations

from typing import Final

SWEDISH: Final = "sv"
ENGLISH: Final = "en"


def language(ha_language: str | None) -> str:
    """Swedish for a Swedish Home Assistant, English otherwise."""
    return SWEDISH if (ha_language or "").lower().startswith("sv") else ENGLISH


#: The page's own words: tabs, headings and the card's buttons.
UI: Final[dict[str, tuple[str, str]]] = {
    "title": ("Ferroamp", "Ferroamp"),
    "overview": ("Översikt", "Overview"),
    "control": ("Styrning", "Control"),
    "system": ("Anläggning", "System"),
    "now": ("Just nu", "Right now"),
    "history": ("Effekt det senaste dygnet", "Power over the last day"),
    "today": ("Energi i dag", "Energy today"),
    "control_entities": ("Styrningen från Home Assistant", "Control from Home Assistant"),
    "in_force": ("Det anläggningen gör nu", "What the system does now"),
    "schedule": ("Schema och FerroAI", "Schedule and FerroAI"),
    "connection": ("Anslutning", "Connection"),
    "software": ("Programvara", "Software"),
    "state_alarms": ("Tillstånd och larm", "State and alarms"),
    "grid": ("Elnätet", "The grid"),
    "strings": ("Solcellerna", "The solar panels"),
    "battery": ("Batteriet", "The battery"),
    "ferroai_price": ("FerroAI och elpriset", "FerroAI and the price"),
    "explain": ("Förklaring", "Explanation"),
    "more_info": ("Öppna i Home Assistant", "Open in Home Assistant"),
    "yes": ("Ja", "Yes"),
    "no": ("Nej", "No"),
    "no_limit": ("ingen gräns", "no limit"),
    "buying": ("köper", "buying"),
    "selling": ("säljer", "selling"),
    "charging": ("laddar", "charging"),
    "discharging": ("laddar ur", "discharging"),
    "still": ("står still", "idle"),
    "none": ("ingen uppgift", "none"),
    "once": ("en gång", "once"),
    "of": ("av", "of"),
    "no_alarms": ("inga", "none"),
    "every_day": ("varje dag", "every day"),
    "every_week": ("varje vecka", "every week"),
    "every_month": ("varje månad", "every month"),
    "every_year": ("varje år", "every year"),
    "day_mo": ("mån", "Mon"),
    "day_tu": ("tis", "Tue"),
    "day_we": ("ons", "Wed"),
    "day_th": ("tors", "Thu"),
    "day_fr": ("fre", "Fri"),
    "day_sa": ("lör", "Sat"),
    "day_su": ("sön", "Sun"),
    "unavailable": ("otillgänglig", "unavailable"),
    "empty": (
        "Ingen Ferroamp-anläggning är igång. Lägg till Ferroamp Cloud Control under "
        "Inställningar, Enheter och tjänster.",
        "No Ferroamp system is running. Add Ferroamp Cloud Control under Settings, "
        "Devices and services.",
    ),
    "failed": (
        "Sidan kunde inte byggas. Felet står i Home Assistants logg.",
        "The page could not be built. The error is in Home Assistant's log.",
    ),
    "source_live": (
        "Ferroamps moln, läst var {interval}:e sekund",
        "Ferroamp's cloud, read every {interval} seconds",
    ),
    "source_slow": (
        "Ferroamps moln, läst var tionde minut",
        "Ferroamp's cloud, read every ten minutes",
    ),
    "source_driver": ("Drivern i Home Assistant", "The driver in Home Assistant"),
}

#: Words for the states the page shows, per entity key or attribute.
WORDS: Final[dict[str, dict[str, tuple[str, str]]]] = {
    "mode_in_force": {
        "self_consumption": ("Egenförbrukning", "Self-consumption"),
        "peak_shaving": ("Kapa effekttoppar", "Peak shaving"),
        "manual": ("Manuellt", "Manual"),
        "measurement": ("Bara mätning", "Measurement only"),
    },
    "control_mode": {
        "self_consumption": ("Egenförbrukning", "Self-consumption"),
        "peak_shaving": ("Kapa effekttoppar", "Peak shaving"),
        "forced_charge": ("Tvångsladdning", "Forced charge"),
        "forced_discharge": ("Tvångsurladdning", "Forced discharge"),
        "idle": ("Vila (lämnar tillbaka)", "Idle (hands back)"),
    },
    "last_command": {
        "idle": ("Vilar", "Idle"),
        "pending": ("Väntar på svar", "Waiting for an answer"),
        "ack": ("Kvitterat", "Accepted"),
        "nak": ("Nekat", "Refused"),
    },
    "origin": {
        "USER": ("Ägaren", "The owner"),
        "FERRO_AI": ("FerroAI", "FerroAI"),
        "SPOT_PRICE_OPTIMIZATION": ("Spotprisoptimering", "Spot price optimisation"),
        "OTHER": ("Ferroamp", "Ferroamp"),
    },
    "schedule_type": {
        "NORMAL": ("Vanligt schema", "Normal schedule"),
        "FALLBACK": ("Standardschema", "Standard schedule"),
    },
    "ferro_state": {
        "running": ("I drift", "Running"),
        "idle": ("Vilar", "Idle"),
        "degraded": ("Nedsatt", "Degraded"),
        "fault": ("Fel", "Fault"),
        "offline": ("Nere", "Offline"),
        "unknown_set_by_ecloud": ("Okänt", "Unknown"),
    },
    "lifecycle": {
        "active": ("Aktiv", "Active"),
        "installed": ("Installerad", "Installed"),
        "planned": ("Planerad", "Planned"),
        "pending": ("Väntar", "Pending"),
        "reconfigure": ("Konfigureras om", "Being reconfigured"),
        "discontinued": ("Avvecklad", "Discontinued"),
    },
    "phases": {
        "one": ("En fas", "One phase"),
        "three": ("Tre faser", "Three phases"),
    },
    "alarm_code": {
        "SYSTEM_OFFLINE": ("Systemet är nere", "The system is offline"),
        "SSO_OFFLINE": ("En solcellsoptimerare är nere", "A solar string optimiser is offline"),
        "ALL": ("Alla", "All"),
    },
    "working": {
        "on": ("Arbetar", "Working"),
        "off": ("Vilar", "Idle"),
    },
    "active_service": {
        "remote_api": ("Remote API (flexleverantör)", "Remote API (flexibility provider)"),
        "ancillary_service": ("Stödtjänster till elnätet", "Ancillary services to the grid"),
    },
    "ferroai_variant": {
        "ferro_optimizer_v1": ("Ferro Optimizer", "Ferro Optimizer"),
        "spot_price_optimization_v1": ("Spotprisoptimering", "Spot price optimisation"),
    },
    "tariff_option": {
        "no_tariff": ("Ingen tidstariff", "No time tariff"),
        "same_tariff_all_day": ("Samma tariff hela dygnet", "The same tariff all day"),
        "weekdays_07_to_20": ("Högre vardagar 07 till 20", "Higher on weekdays 07 to 20"),
        "all_days_07_to_20": ("Högre alla dagar 07 till 20", "Higher every day 07 to 20"),
        "reducted_tariff_at_night": ("Lägre på natten", "Lower at night"),
        "reduced_x2_20_to_07": ("Sänkt (x2) 20 till 07", "Reduced (x2) 20 to 07"),
    },
    "on_off": {
        "on": ("På", "On"),
        "off": ("Av", "Off"),
    },
    "online": {
        "on": ("Uppkopplad", "Online"),
        "off": ("Nere", "Offline"),
    },
    "following": {
        "on": ("Molnet tog emot", "The cloud accepted"),
        "off": ("Molnet vägrade", "The cloud refused"),
    },
}

#: The name every value goes by on the page, by the same keys as EXPLAIN. A
#: name a person gave an entity in Home Assistant goes before its name here.
NAMES: Final[dict[str, tuple[str, str]]] = {
    "solar_power": ("Sol", "Solar"),
    "consumption_power": ("Förbrukning", "Consumption"),
    "grid_power": ("Nät", "Grid"),
    "battery_power": ("Batteri", "Battery"),
    "soc": ("Laddnivå", "State of charge"),
    "solar_energy_today": ("Solenergi", "Solar"),
    "consumption_energy_today": ("Förbrukning", "Consumption"),
    "grid_import_energy_today": ("Köpt från nätet", "Bought from the grid"),
    "grid_export_energy_today": ("Sålt till nätet", "Sold to the grid"),
    "battery_charged_energy_today": ("Laddat i batteriet", "Charged into the battery"),
    "battery_discharged_energy_today": ("Urladdat ur batteriet", "Discharged from the battery"),
    "control_enabled": ("Styrning", "Control"),
    "mode": ("Läge", "Mode"),
    "battery_power_setpoint": ("Börvärde för batteriet", "Battery setpoint"),
    "grid_power_limit": ("Gräns för köp", "Purchase limit"),
    "following": ("Följer", "Following"),
    "last_command": ("Senaste kommando", "Last command"),
    "last_command.reason": ("Orsak", "Reason"),
    "system_mode": ("Driftläge", "Operating mode"),
    "system_mode.pv_on": ("Solceller på", "Solar on"),
    "system_mode.phase_balancing_on": ("Fasbalansering (ACE)", "Phase balancing (ACE)"),
    "system_mode.phase_balancing_threshold_a": ("Gräns för fasbalansering", "Phase balancing limit"),
    "system_mode.limit_import": ("Begränsa köp", "Limit purchase"),
    "system_mode.limit_export": ("Begränsa försäljning", "Limit sales"),
    "system_mode.threshold_high_w": ("Övre tröskel mot nätet", "Upper grid threshold"),
    "system_mode.threshold_low_w": ("Undre tröskel mot nätet", "Lower grid threshold"),
    "system_mode.charge_reference_w": ("Laddeffekt", "Charging power"),
    "system_mode.discharge_reference_w": ("Urladdningseffekt", "Discharging power"),
    "system_mode.soc_low": ("Lägsta laddnivå", "Lowest charge"),
    "system_mode.soc_high": ("Högsta laddnivå", "Highest charge"),
    "active_schedule": ("Aktivt schema", "Active schedule"),
    "active_schedule.origin": ("Från", "From"),
    "active_schedule.schedule_type": ("Sort", "Kind"),
    "active_schedule.start": ("Start", "Start"),
    "active_schedule.end": ("Slut", "End"),
    "active_schedule.rrule": ("Upprepning", "Repeats"),
    "active_schedule.applied_at": ("Utlagt", "Laid out"),
    "ferroai": ("FerroAI", "FerroAI"),
    "ferroai_action": ("FerroAI gör", "FerroAI is doing"),
    "online": ("Uppkoppling", "Connection"),
    "last_seen": ("Senast hörd", "Last heard from"),
    "battery_capacity": ("Kapacitet", "Capacity"),
    "max_charge_power": ("Märkeffekt", "Rated power"),
    "firmware_version": ("Systemets version", "System version"),
    "firmware_version.controller_version": ("Styrdatorns version", "Controller version"),
    "firmware_version.controller_generation": ("Styrdatorns generation", "Controller generation"),
    "firmware_version.last_update_to": ("Senast uppdaterad till", "Last updated to"),
    "firmware_version.last_update_from": ("Uppdaterad från", "Updated from"),
    "firmware_version.last_update_at": ("Uppdaterad", "Updated"),
    "firmware_version.hostname": ("Värdnamn", "Host name"),
    "system_state": ("Systemets tillstånd", "System state"),
    "system_state.since": ("Sedan", "Since"),
    "system_state.lifecycle": ("Livscykel", "Life cycle"),
    "system_state.main_fuse_a": ("Huvudsäkring", "Main fuse"),
    "system_state.phases": ("Faser", "Phases"),
    "system_state.inverter_power_rating_w": ("Växelriktarens märkeffekt", "Inverter rated power"),
    "system_state.eso_generation": ("Batteriomvandlare (ESO)", "Battery converter (ESO)"),
    "active_alarms": ("Aktiva larm", "Active alarms"),
    "active_alarms.alarms": ("Larmen", "The alarms"),
    "grid_voltage_l1": ("Spänning L1", "Voltage L1"),
    "grid_voltage_l2": ("Spänning L2", "Voltage L2"),
    "grid_voltage_l3": ("Spänning L3", "Voltage L3"),
    "grid_current_l1": ("Ström L1", "Current L1"),
    "grid_current_l2": ("Ström L2", "Current L2"),
    "grid_current_l3": ("Ström L3", "Current L3"),
    "phase_balancing_active": ("Fasbalansering just nu", "Phase balancing now"),
    "phase_balancing_active.ace_correction_l1": ("Korrigering L1", "Correction L1"),
    "phase_balancing_active.ace_correction_l2": ("Korrigering L2", "Correction L2"),
    "phase_balancing_active.ace_correction_l3": ("Korrigering L3", "Correction L3"),
    "grid_power_l1": ("Näteffekt L1", "Grid power L1"),
    "grid_power_l2": ("Näteffekt L2", "Grid power L2"),
    "grid_power_l3": ("Näteffekt L3", "Grid power L3"),
    "consumption_power_l1": ("Förbrukning L1", "Consumption L1"),
    "consumption_power_l2": ("Förbrukning L2", "Consumption L2"),
    "consumption_power_l3": ("Förbrukning L3", "Consumption L3"),
    "system_state.active_services": ("Externa tjänster", "Outside services"),
    "ferroai.variant": ("Optimering", "Optimisation"),
    "ferroai.activated_at": ("Påslagen sedan", "On since"),
    "ferroai.tariff_option": ("Nättariff", "Grid tariff"),
    "ferroai.minimum_earnings": ("Minsta vinst", "Minimum earnings"),
    "ferroai.limit_import_threshold": ("FerroAI:s köpgräns", "FerroAI's import limit"),
    "ferroai.limit_export_threshold": ("FerroAI:s säljgräns", "FerroAI's export limit"),
    "ferroai.bidding_zone": ("Elområde", "Bidding zone"),
    "spot_price": ("Spotpris nu", "Spot price now"),
    "forecast_soc": ("Prognos för laddnivån", "Forecast state of charge"),
    "forecast_soc.solar_w": ("Prognos för solen", "Forecast solar"),
    "forecast_soc.consumption_w": ("Prognos för förbrukningen", "Forecast consumption"),
    "battery_state": ("Tillstånd", "State"),
    "battery_state.reasons": ("Orsaker", "Reasons"),
    "battery_health": ("Hälsa (SoH)", "Health (SoH)"),
    "battery_health.manufacturer": ("Tillverkare", "Manufacturer"),
    "battery_health.battery_voltage_v": ("Batterispänning", "Battery voltage"),
    "battery_health.battery_current_a": ("Batteriström", "Battery current"),
    "battery_health.cell_voltage_min_v": ("Lägsta cellspänning", "Lowest cell voltage"),
    "battery_health.cell_voltage_max_v": ("Högsta cellspänning", "Highest cell voltage"),
    "battery_cell_temperature_min": ("Lägsta celltemperatur", "Lowest cell temperature"),
    "battery_cell_temperature_max": ("Högsta celltemperatur", "Highest cell temperature"),
    "solar_strings": ("Strängar i drift", "Strings running"),
    "solar_strings.strings": ("Strängarna", "The strings"),
}

#: What every value and option is, by the page's key for it. A key is an
#: entity key, or an entity key and an attribute joined by a dot.
EXPLAIN: Final[dict[str, tuple[str, str]]] = {
    # ------------------------------------------------------------- right now
    "solar_power": (
        "Vad solcellerna ger just nu, summerat över alla strängar. Anläggningen mäter och "
        "skickar ett nytt värde till Ferroamps moln var 15:e sekund.",
        "What the solar panels give right now, summed over all strings. The system measures "
        "it and sends a new value to Ferroamp's cloud every 15 seconds.",
    ),
    "system_state.active_services": (
        "Tjänster utanför Ferroamp som är aktiva för anläggningen: en flexleverantörs Remote "
        "API eller stödtjänster till elnätet. När en sådan styr kan varken ägaren eller FerroAI "
        "styra fullt ut.",
        "Services outside Ferroamp that are active for the system: a flexibility provider's "
        "Remote API or ancillary services to the grid. While one of them steers, neither the "
        "owner nor FerroAI can steer fully.",
    ),
    "consumption_power": (
        "Vad huset förbrukar just nu, utan batteriets laddning. Det är effekten till husets "
        "egna laster, oavsett om den kommer från solen, batteriet eller nätet.",
        "What the house uses right now, not counting the battery's charging. It is the power "
        "going to the house's own loads, whether it comes from the sun, the battery or the grid.",
    ),
    "grid_power": (
        "Utbytet med elnätet. Plus betyder att huset köper el, minus att det säljer. Det är "
        "samma tecken som EMS och Home Assistants energipanel räknar med.",
        "The exchange with the grid. Plus means the house is buying, minus that it is selling. "
        "It is the sign EMS and Home Assistant's energy dashboard work with.",
    ),
    "battery_power": (
        "Batteriets effekt. Plus betyder att batteriet laddar ur och ger el till huset eller "
        "nätet, minus att det laddar. Det är Ferroamps eget tecken, samma som i den lokala "
        "Ferroamp-integrationen; EMS vänder det med sin inställning för batteriets tecken.",
        "The battery's power. Plus means the battery is discharging, giving power to the house "
        "or the grid, minus that it is charging. It is Ferroamp's own sign, as in the local "
        "Ferroamp integration; EMS turns it round with its battery sign setting.",
    ),
    "soc": (
        "Hur fullt batteriet är, i procent. Värdet kommer från batterisystemet via Ferroamps "
        "moln och ändras långsammare än effekterna, oftast en procentenhet i taget.",
        "How full the battery is, in percent. The value comes from the battery system through "
        "Ferroamp's cloud and changes more slowly than the powers, usually one point at a time.",
    ),
    # ----------------------------------------------------------------- today
    "solar_energy_today": (
        "Solenergi sedan midnatt, i kWh. Summeras ur molnets timserie och läses var tionde "
        "minut, så den senaste timmen kan ligga lite efter. Börjar om vid midnatt.",
        "Solar energy since midnight, in kWh. Summed from the cloud's hourly series and read "
        "every ten minutes, so the latest hour can lag a little. Starts again at midnight.",
    ),
    "consumption_energy_today": (
        "Husets förbrukning sedan midnatt, i kWh, utan batteriets laddning. Läses var tionde "
        "minut och börjar om vid midnatt.",
        "The house's use since midnight, in kWh, not counting the battery's charging. Read "
        "every ten minutes; starts again at midnight.",
    ),
    "grid_import_energy_today": (
        "El köpt från nätet sedan midnatt, i kWh. Det är den som Home Assistants energipanel "
        "använder som köpt el. Läses var tionde minut.",
        "Energy bought from the grid since midnight, in kWh. Home Assistant's energy "
        "dashboard uses it as grid consumption. Read every ten minutes.",
    ),
    "grid_export_energy_today": (
        "El såld till nätet sedan midnatt, i kWh. Läses var tionde minut.",
        "Energy sold to the grid since midnight, in kWh. Read every ten minutes.",
    ),
    "battery_charged_energy_today": (
        "Energi in i batteriet sedan midnatt, i kWh, från solen eller nätet. Läses var tionde "
        "minut.",
        "Energy into the battery since midnight, in kWh, from the sun or the grid. Read every "
        "ten minutes.",
    ),
    "battery_discharged_energy_today": (
        "Energi ur batteriet sedan midnatt, i kWh. Skillnaden mot laddat är förluster plus "
        "förändringen i laddnivå. Läses var tionde minut.",
        "Energy out of the battery since midnight, in kWh. The difference to what was charged "
        "is losses plus the change in charge. Read every ten minutes.",
    ),
    # --------------------------------------------------------------- control
    "control_enabled": (
        "Huvudbrytaren för styrningen. Av: drivern skriver ingenting till Ferroamps moln och "
        "anläggningen följer sina egna scheman. På: drivern lägger ut börvärdet nedan som "
        "scheman. När den slås av lämnas anläggningen tillbaka direkt, med ägarens egen "
        "inställning. Den är av efter installationen.",
        "The main switch for control. Off: the driver writes nothing to Ferroamp's cloud and "
        "the system follows its own schedules. On: the driver lays out the setpoint below as "
        "schedules. Turning it off hands the system back at once, with the owner's own "
        "configuration. It is off after installation.",
    ),
    "mode": (
        "Läget enligt EMS växelriktarkontrakt, samma lägen som i den lokala Ferroamp-drivern. "
        "Vila lämnar tillbaka batteriet till ägarens inställning, vad börvärdet än säger. De "
        "andra lägena följer börvärdet; molnets egna lägen för egenförbrukning och "
        "effekttoppar används inte av drivern.",
        "The mode of the EMS inverter contract, the same modes as in the local Ferroamp driver. "
        "Idle hands the battery back to the owner's configuration, whatever the setpoint says. "
        "The other modes follow the setpoint; the cloud's own self-consumption and peak shaving "
        "configurations are not used by the driver.",
    ),
    "battery_power_setpoint": (
        "Börvärdet för batteriet i W, som EMS skriver varje gång den planerar. Plus laddar med "
        "den effekten, minus laddar ur, 0 lämnar tillbaka till ägarens inställning. Ett "
        "kommando blir ett manuellt schema från nästa hela minut i tio minuter, följt av ett "
        "schema som återställer ägarens inställning. Det förnyas var femte minut; slutar "
        "förnyelserna tar ägarens inställning över av sig själv.",
        "The battery's setpoint in W, written by EMS every time it plans. Plus charges at that "
        "power, minus discharges, 0 hands back to the owner's configuration. A command becomes "
        "a manual schedule from the next whole minute, for ten minutes, followed by a schedule "
        "that brings back the owner's configuration. It is renewed every five minutes; if the "
        "renewals stop, the owner's configuration takes over on its own.",
    ),
    "grid_power_limit": (
        "Den gräns för köp från nätet som EMS planerar med, i W. Den sparas och visas, men "
        "skickas aldrig till molnet, som inte har något sådant kommando här. Maxvärdet "
        "betyder ingen gräns.",
        "The limit on buying from the grid that EMS plans with, in W. It is kept and shown but "
        "never sent to the cloud, which has no such command here. The maximum means no limit.",
    ),
    "following": (
        "På när molnet tog emot drivarens senaste skrivning, av när det vägrade; orsaken står "
        "under Senaste kommando. Tomt innan något har skrivits. EMS larmar under Reparationer "
        "om molnet vägrar flera gånger i rad.",
        "On when the cloud accepted the driver's latest write, off when it refused it; the "
        "reason is under Last command. Empty before anything has been written. EMS raises a "
        "Repairs issue when the cloud refuses several times in a row.",
    ),
    "last_command": (
        "Vad drivern senast bad molnet om och hur det gick. Vilar: inget skickat, eller "
        "styrningen är av. Väntar på svar: skickat nyss. Kvitterat: molnet tog emot schemana. "
        "Nekat: molnet vägrade, eller de kunde inte läggas ut.",
        "What the driver last asked the cloud for and how it went. Idle: nothing sent, or "
        "control is off. Waiting for an answer: just sent. Accepted: the cloud took the "
        "schedules. Refused: the cloud said no, or they could not be laid out.",
    ),
    "last_command.reason": (
        "Varför det senaste blev som det blev, när det finns något att säga: till exempel att "
        "FerroAI är på, att molnet inte svarade, att ett gammalt schema inte kunde tas bort, "
        "eller att ägarens inställning är tillbaka efter att styrningen slagits av.",
        "Why the last result was what it was, when there is something to say: for instance "
        "that FerroAI is on, that the cloud did not answer, that an old schedule could not be "
        "removed, or that the owner's configuration is back after control was turned off.",
    ),
    # --------------------------------------------------------------- in force
    "system_mode": (
        "Den inställning anläggningen kör just nu, som molnet rapporterar den. Egenförbrukning: "
        "batteriet täcker husets behov och laddas av överskott. Kapa effekttoppar: batteriet "
        "håller köpet från nätet inom trösklarna nedan. Manuellt: batteriet laddar eller laddar "
        "ur med fast effekt; så ser drivarens kommandon ut. Bara mätning: batteriet står still.",
        "The configuration the system runs right now, as the cloud reports it. Self-consumption: "
        "the battery covers the house and is charged by surplus. Peak shaving: the battery keeps "
        "the purchase from the grid within the thresholds below. Manual: the battery charges or "
        "discharges at a fixed power; that is what the driver's commands look like. Measurement "
        "only: the battery stands still.",
    ),
    "system_mode.pv_on": (
        "Om solcellerna får producera. Nej stänger av solproduktionen helt.",
        "Whether the solar panels may produce. No switches solar production off entirely.",
    ),
    "system_mode.phase_balancing_on": (
        "Fasbalansering (ACE): växelriktaren flyttar ström mellan faserna så att ingen fas mot "
        "nätet går över gränsen nedan. Skyddar huvudsäkringarna när en fas är hårt belastad.",
        "Phase balancing (ACE): the inverter moves current between the phases so that no phase "
        "towards the grid goes above the limit below. It protects the main fuses when one phase "
        "is heavily loaded.",
    ),
    "system_mode.phase_balancing_threshold_a": (
        "Den ström per fas mot nätet, i A, som fasbalanseringen håller sig under.",
        "The current per phase towards the grid, in A, that phase balancing keeps below.",
    ),
    "system_mode.limit_import": (
        "Om köpet från nätet begränsas till den övre tröskeln.",
        "Whether buying from the grid is limited to the upper threshold.",
    ),
    "system_mode.limit_export": (
        "Om försäljningen till nätet begränsas av den undre tröskeln. Används till exempel när "
        "nätägaren inte tar emot mer än en viss effekt.",
        "Whether selling to the grid is limited by the lower threshold. Used for instance where "
        "the grid owner takes no more than a certain power.",
    ),
    "system_mode.threshold_high_w": (
        "Övre tröskel mot nätet, i W. I Kapa effekttoppar: köpet som batteriet ska hålla sig "
        "under, det laddar ur när köpet går över. Med importbegränsning: taket för köp.",
        "Upper threshold towards the grid, in W. In peak shaving: the purchase the battery "
        "keeps below, discharging when it goes above. With import limit: the cap on buying.",
    ),
    "system_mode.threshold_low_w": (
        "Undre tröskel mot nätet, i W. I Kapa effekttoppar: när köpet är under den här nivån "
        "får batteriet ladda från nätet. I Egenförbrukning anger den hur mycket som får säljas; "
        "minus en miljon betyder ingen gräns.",
        "Lower threshold towards the grid, in W. In peak shaving: when the purchase is below "
        "this level, the battery may charge from the grid. In self-consumption it says how much "
        "may be sold; minus a million means no limit.",
    ),
    "system_mode.charge_reference_w": (
        "Högsta laddeffekt, i W. 100 000 betyder ingen egen gräns, batteriets egen högsta "
        "effekt gäller. I Manuellt läge: den effekt batteriet laddar med.",
        "Highest charging power, in W. 100 000 means no limit of its own; the battery's own "
        "maximum applies. In manual mode: the power the battery charges at.",
    ),
    "system_mode.discharge_reference_w": (
        "Högsta urladdningseffekt, i W. 100 000 betyder ingen egen gräns. I Manuellt läge: den "
        "effekt batteriet laddar ur med.",
        "Highest discharging power, in W. 100 000 means no limit of its own. In manual mode: "
        "the power the battery discharges at.",
    ),
    "system_mode.soc_low": (
        "Lägsta laddnivå, i procent, som batteriet laddas ur till. Under den står batteriet "
        "kvar som reserv.",
        "Lowest charge, in percent, the battery is discharged to. Below it the battery is kept "
        "in reserve.",
    ),
    "system_mode.soc_high": (
        "Högsta laddnivå, i procent, som batteriet laddas till.",
        "Highest charge, in percent, the battery is charged to.",
    ),
    # --------------------------------------------------------------- schedule
    "active_schedule": (
        "Det schema som molnet senast markerade som aktivt. Listan läses var tionde minut, så "
        "ett nytt schema kan synas här upp till tio minuter efter att driftläget ovan redan har "
        "bytt. Drivarens egna scheman heter EMS control.",
        "The schedule the cloud last marked as active. The list is read every ten minutes, so a "
        "new schedule can show here up to ten minutes after the mode above has already changed. "
        "The driver's own schedules are called EMS control.",
    ),
    "active_schedule.origin": (
        "Vem schemat kommer från: ägaren, lagt i appen eller av drivern, FerroAI, "
        "spotprisoptimering, eller Ferroamp, som står för standardschemana.",
        "Where the schedule comes from: the owner, laid out in the app or by the driver, "
        "FerroAI, spot price optimisation, or Ferroamp, which provides the standard schedules.",
    ),
    "active_schedule.schedule_type": (
        "Vanligt schema eller standardschema. Standardschemat gäller när inget annat gör: "
        "egenförbrukning på sommaren och kapa effekttoppar på vintern.",
        "Normal or standard schedule. The standard schedule applies when nothing else does: "
        "self-consumption in summer and peak shaving in winter.",
    ),
    "active_schedule.start": (
        "När schemat började, första gången för ett återkommande schema.",
        "When the schedule began, the first time for a recurring schedule.",
    ),
    "active_schedule.end": (
        "När schemat slutar. Observera att slutet inte återställer något: inställningen står "
        "kvar tills nästa schema startar. Därför lägger drivern alltid ett schema efter sitt "
        "eget som återställer ägarens inställning.",
        "When the schedule ends. Note that the end resets nothing: the configuration stays "
        "until the next schedule starts. That is why the driver always lays out a schedule "
        "after its own that brings back the owner's configuration.",
    ),
    "active_schedule.rrule": (
        "Hur schemat upprepas, i iCalendar-form, till exempel varje vecka måndag till söndag. "
        "Tomt för ett schema som bara gäller en gång.",
        "How the schedule repeats, in iCalendar form, for instance every week Monday to Sunday. "
        "Empty for a schedule that applies once.",
    ),
    "active_schedule.applied_at": (
        "När molnet senast lade ut schemat på anläggningen, normalt inom en sekund efter "
        "schemats start.",
        "When the cloud last laid the schedule out on the system, normally within a second of "
        "the schedule's start.",
    ),
    "ferroai": (
        "Om FerroAI, Ferroamps egen optimering mot elpriset, styr anläggningen. När den är på "
        "vägrar molnet ägarens egna scheman, och därmed också drivarens styrning.",
        "Whether FerroAI, Ferroamp's own optimisation against the electricity price, runs the "
        "system. While it is on the cloud refuses the owner's own schedules, and so the "
        "driver's control too.",
    ),
    "ferroai_action": (
        "Vad FerroAI gör just nu, när den är på: till exempel laddar, laddar ur eller kapar "
        "toppar. Tomt när FerroAI är av.",
        "What FerroAI is doing right now, while it is on: for instance charging, discharging or "
        "peak shaving. Empty while FerroAI is off.",
    ),
    "ferroai.variant": (
        "Vilket slags optimering FerroAI kör: Ferroamps egen optimerare eller enbart mot "
        "spotpriset. Läses var tionde minut.",
        "Which kind of optimisation FerroAI runs: Ferroamp's own optimiser or against the spot "
        "price alone. Read every ten minutes.",
    ),
    "ferroai.activated_at": (
        "När FerroAI senast slogs på för anläggningen, enligt molnet.",
        "When FerroAI was last switched on for the system, according to the cloud.",
    ),
    "ferroai.tariff_option": (
        "Den tidstariff för elnätet som ägaren har valt i appen, som FerroAI räknar med när "
        "den planerar.",
        "The grid's time tariff the owner chose in the app, which FerroAI counts on when it "
        "plans.",
    ),
    "ferroai.minimum_earnings": (
        "Den minsta vinst som ägaren har valt i appen för att FerroAI ska ladda och ladda ur, "
        "som appen anger den.",
        "The smallest gain the owner chose in the app for FerroAI to charge and discharge, as "
        "the app gives it.",
    ),
    "ferroai.limit_import_threshold": (
        "Den gräns för köp från nätet som FerroAI håller sig under, som appen anger den. "
        "Det är FerroAI:s inställning, inte drivarens gräns på fliken Styrning.",
        "The limit for buying from the grid that FerroAI keeps below, as the app gives it. It is "
        "FerroAI's setting, not the driver's limit on the Control tab.",
    ),
    "ferroai.limit_export_threshold": (
        "Den gräns för försäljning till nätet som FerroAI håller sig under, som appen anger den.",
        "The limit for selling to the grid that FerroAI keeps below, as the app gives it.",
    ),
    "ferroai.bidding_zone": (
        "Elområdet som anläggningens spotpris hämtas för, till exempel SE3.",
        "The bidding zone the system's spot price is fetched for, for instance SE3.",
    ),
    "spot_price": (
        "Spotpriset för den här perioden, det pris anläggningen optimeras mot, i den valuta "
        "appen visar per kWh. Attributen har dagens priser och morgondagens när de finns. "
        "Läses var tionde minut.",
        "The spot price for this period, the price the system is optimised against, in the "
        "currency the app shows, per kWh. The attributes hold today's prices, and tomorrow's "
        "once they are out. Read every ten minutes.",
    ),
    "forecast_soc": (
        "Den laddnivå FerroAI räknar med för den här timmen, i %. Hela prognosen, timme för "
        "timme ungefär ett och ett halvt dygn framåt, finns i attributen. Tomt när molnet "
        "inte har någon prognos.",
        "The state of charge FerroAI expects for this hour, in %. The whole forecast, hour by "
        "hour about a day and a half ahead, is in the attributes. Empty while the cloud has "
        "no forecast.",
    ),
    "forecast_soc.solar_w": (
        "Den solproduktion FerroAI räknar med för den här timmen, i W.",
        "The solar production FerroAI expects for this hour, in W.",
    ),
    "forecast_soc.consumption_w": (
        "Den förbrukning FerroAI räknar med för den här timmen, i W.",
        "The consumption FerroAI expects for this hour, in W.",
    ),
    # ----------------------------------------------------------------- software
    "firmware_version": (
        "Versionen av EnergyHubens operativsystem, som molnet anger den. ESO 15 kräver version 7 "
        "eller senare. Ferroamp uppdaterar den själva, utan att ägaren behöver göra något.",
        "The version of the EnergyHub's operating system, as the cloud gives it. An ESO 15 needs "
        "version 7 or later. Ferroamp updates it themselves, without the owner doing anything.",
    ),
    "firmware_version.controller_version": (
        "Versionen på EnergyHubens egen dator, den som talar med molnet. Oftast samma som "
        "systemets version.",
        "The version on the EnergyHub's own computer, the one that talks to the cloud. Usually the "
        "same as the system's version.",
    ),
    "firmware_version.controller_generation": (
        "Vilken sorts dator EnergyHuben har: CORE i nyare system, BBB (BeagleBone) i äldre.",
        "Which kind of computer the EnergyHub has: CORE in newer systems, BBB (BeagleBone) in older.",
    ),
    "firmware_version.last_update_to": (
        "Den version anläggningen senast uppdaterades till, enligt styrdatorns logg.",
        "The version the system was last updated to, according to the controller's log.",
    ),
    "firmware_version.last_update_from": (
        "Den version anläggningen hade före den senaste uppdateringen.",
        "The version the system had before the latest update.",
    ),
    "firmware_version.last_update_at": (
        "När Ferroamp senast uppdaterade anläggningens programvara, enligt molnet.",
        "When Ferroamp last updated the system's software, according to the cloud.",
    ),
    "firmware_version.hostname": (
        "EnergyHubens namn i nätverket, som Ferroamp har satt det.",
        "The EnergyHub's name on the network, as Ferroamp has set it.",
    ),
    # ------------------------------------------------------------ state, alarms
    "system_state": (
        "Hela systemets tillstånd enligt Ferroamp. I drift: allt fungerar. Vilar: inget att göra "
        "just nu. Nedsatt: systemet går men någon del fungerar inte fullt ut. Fel: något har "
        "stoppat. Samma besked som i Ferroamps app.",
        "The whole system's state according to Ferroamp. Running: all is well. Idle: nothing to do "
        "right now. Degraded: the system runs, but some part does not work fully. Fault: something "
        "has stopped. The same word as in Ferroamp's app.",
    ),
    "system_state.since": (
        "När systemet kom i det tillstånd det har nu.",
        "When the system came into the state it is in now.",
    ),
    "system_state.lifecycle": (
        "Var anläggningen är i Ferroamps register: planerad, installerad, aktiv, under omkonfigurering "
        "eller avvecklad. En anläggning i drift är aktiv.",
        "Where the system is in Ferroamp's register: planned, installed, active, being reconfigured "
        "or discontinued. A system in use is active.",
    ),
    "system_state.main_fuse_a": (
        "Huvudsäkringens storlek i A, som installatören har angett den. Fasbalanseringen och "
        "importtaket räknar med den.",
        "The main fuse's size in A, as the installer entered it. Phase balancing and the import "
        "cap work with it.",
    ),
    "system_state.phases": (
        "Om anläggningen är ansluten med en eller tre faser.",
        "Whether the system is connected with one phase or three.",
    ),
    "system_state.inverter_power_rating_w": (
        "Växelriktarens märkeffekt i W, alltså hur mycket EnergyHuben kan ge eller ta mot nätet.",
        "The inverter's rated power in W, that is how much the EnergyHub can give to or take from "
        "the grid.",
    ),
    "system_state.eso_generation": (
        "Vilken batteriomvandlare (ESO) systemet har: ESO6 eller ESO15. ESO15 kräver EnergyHub OS 7 "
        "eller senare, och det är därför den här integrationen behövs.",
        "Which battery converter (ESO) the system has: ESO6 or ESO15. An ESO15 needs EnergyHub OS 7 "
        "or later, which is why this integration is needed.",
    ),
    "active_alarms": (
        "Hur många larm som är aktiva just nu. Ferroamps larm gäller att systemet eller en "
        "solcellsoptimerare (SSO) har tappat kontakten.",
        "How many alarms are active right now. Ferroamp's alarms are about the system or a solar "
        "string optimiser (SSO) having lost contact.",
    ),
    "active_alarms.alarms": (
        "Varje aktivt larm: vad det gäller, vilken enhet och sedan när.",
        "Every active alarm: what it is about, which unit and since when.",
    ),
    # ------------------------------------------------------------------- grid
    "grid_voltage_l1": (
        "Nätets spänning på fas L1 vid anslutningen, i V. Normalt runt 230 V.",
        "The grid's voltage on phase L1 at the connection, in V. Normally around 230 V.",
    ),
    "grid_voltage_l2": (
        "Nätets spänning på fas L2 vid anslutningen, i V.",
        "The grid's voltage on phase L2 at the connection, in V.",
    ),
    "grid_voltage_l3": (
        "Nätets spänning på fas L3 vid anslutningen, i V.",
        "The grid's voltage on phase L3 at the connection, in V.",
    ),
    "grid_current_l1": (
        "Strömmen på fas L1 mot nätet, i A, som effektivvärde. Det är den som går genom "
        "huvudsäkringen och som fasbalanseringen håller under sin gräns.",
        "The current on phase L1 towards the grid, in A (RMS). It is what passes the main fuse and "
        "what phase balancing keeps below its limit.",
    ),
    "grid_current_l2": (
        "Strömmen på fas L2 mot nätet, i A, som effektivvärde.",
        "The current on phase L2 towards the grid, in A (RMS).",
    ),
    "grid_current_l3": (
        "Strömmen på fas L3 mot nätet, i A, som effektivvärde.",
        "The current on phase L3 towards the grid, in A (RMS).",
    ),
    "phase_balancing_active": (
        "Om fasbalanseringen (ACE) flyttar ström mellan faserna just nu, för att hålla den mest "
        "belastade fasen under gränsen.",
        "Whether phase balancing (ACE) is moving current between the phases right now, to keep the "
        "most loaded phase below the limit.",
    ),
    "phase_balancing_active.ace_correction_l1": (
        "Hur mycket ström fasbalanseringen flyttar på fas L1 just nu, i A, som Ferroamp anger "
        "den. Noll när den vilar. Attributen har också strömmen före och efter korrigeringen.",
        "How much current phase balancing moves on phase L1 right now, in A, as Ferroamp gives "
        "it. Zero while it rests. The attributes also hold the current before and after.",
    ),
    "phase_balancing_active.ace_correction_l2": (
        "Hur mycket ström fasbalanseringen flyttar på fas L2 just nu, i A.",
        "How much current phase balancing moves on phase L2 right now, in A.",
    ),
    "phase_balancing_active.ace_correction_l3": (
        "Hur mycket ström fasbalanseringen flyttar på fas L3 just nu, i A.",
        "How much current phase balancing moves on phase L3 right now, in A.",
    ),
    "grid_power_l1": (
        "Effekten mot nätet på fas L1, i W. Positiv när fasen köper, negativ när den säljer. "
        "Faserna mäts var för sig, så en fas kan sälja medan en annan köper.",
        "The power towards the grid on phase L1, in W. Positive while the phase buys, negative "
        "while it sells. Each phase is measured on its own, so one can sell while another buys.",
    ),
    "grid_power_l2": (
        "Effekten mot nätet på fas L2, i W. Positiv vid köp, negativ vid försäljning.",
        "The power towards the grid on phase L2, in W. Positive when buying, negative when selling.",
    ),
    "grid_power_l3": (
        "Effekten mot nätet på fas L3, i W. Positiv vid köp, negativ vid försäljning.",
        "The power towards the grid on phase L3, in W. Positive when buying, negative when selling.",
    ),
    "consumption_power_l1": (
        "Husets förbrukning på fas L1, i W, som EnergyHuben räknar fram den. Visar vilken fas "
        "de stora lasterna ligger på.",
        "The house's consumption on phase L1, in W, as the EnergyHub works it out. It shows which "
        "phase the large loads are on.",
    ),
    "consumption_power_l2": (
        "Husets förbrukning på fas L2, i W, som EnergyHuben räknar fram den.",
        "The house's consumption on phase L2, in W, as the EnergyHub works it out.",
    ),
    "consumption_power_l3": (
        "Husets förbrukning på fas L3, i W, som EnergyHuben räknar fram den.",
        "The house's consumption on phase L3, in W, as the EnergyHub works it out.",
    ),
    # ---------------------------------------------------------------- battery
    "battery_state": (
        "Batteriets tillstånd enligt Ferroamp. Med flera batterier visas det sämsta.",
        "The battery's state according to Ferroamp. With several batteries, the worst one shows.",
    ),
    "battery_state.reasons": (
        "Batteriets egna koder för vad det gör eller varför det är begränsat, till exempel "
        "underhållsladdning eller nedstämpling av effekten vid låg laddnivå eller hög temperatur. "
        "Koderna visas som Ferroamp skriver dem.",
        "The battery's own codes for what it does or why it is limited, for instance a maintenance "
        "charge or power derated at a low charge or a high temperature. The codes show as Ferroamp "
        "writes them.",
    ),
    "battery_health": (
        "Batteriets hälsa (state of health) i procent: hur mycket av den ursprungliga kapaciteten "
        "som finns kvar. Med flera batterier visas det svagaste.",
        "The battery's state of health in percent: how much of its original capacity is left. With "
        "several batteries, the weakest one shows.",
    ),
    "battery_health.manufacturer": (
        "Batteriets tillverkare, som Ferroamp har registrerat den.",
        "The battery's manufacturer, as Ferroamp has registered it.",
    ),
    "battery_health.battery_voltage_v": (
        "Batteriets spänning i V, mätt av batterisystemet.",
        "The battery's voltage in V, measured by the battery system.",
    ),
    "battery_health.battery_current_a": (
        "Batteriets ström i A, mätt av batterisystemet. Tecknet följer batteriets egen mätning.",
        "The battery's current in A, measured by the battery system. The sign follows the battery's "
        "own measurement.",
    ),
    "battery_health.cell_voltage_min_v": (
        "Den lägsta spänningen bland batteriets celler, i V. En stor skillnad mot den högsta kan "
        "tyda på att cellerna behöver balanseras.",
        "The lowest voltage among the battery's cells, in V. A large gap to the highest can mean "
        "the cells need balancing.",
    ),
    "battery_health.cell_voltage_max_v": (
        "Den högsta spänningen bland batteriets celler, i V.",
        "The highest voltage among the battery's cells, in V.",
    ),
    "battery_cell_temperature_min": (
        "Den lägsta temperaturen bland batteriets celler, i °C. Ett kallt batteri tar emot och "
        "ger mindre effekt.",
        "The lowest temperature among the battery's cells, in °C. A cold battery takes and gives "
        "less power.",
    ),
    "battery_cell_temperature_max": (
        "Den högsta temperaturen bland batteriets celler, i °C. Blir den för hög stämplar batteriet "
        "ner effekten.",
        "The highest temperature among the battery's cells, in °C. If it gets too high, the battery "
        "derates its power.",
    ),
    # ---------------------------------------------------------------- strings
    "solar_strings": (
        "Hur många av solcellsoptimerarna (SSO), en per sträng, som är i drift just nu. På natten "
        "går de ner, så färre i drift då är normalt.",
        "How many of the solar string optimisers (SSO), one per string, are running right now. They "
        "go down at night, so fewer running then is normal.",
    ),
    "solar_strings.strings": (
        "Varje sträng med sitt namn i appen, sitt tillstånd och sin märkeffekt.",
        "Every string with its name in the app, its state and its rated power.",
    ),
    # ----------------------------------------------------------------- system
    "online": (
        "Molnets eget besked om att anläggningen rapporterar in. Nere betyder att molnet inte "
        "har hört av den på en stund, till exempel vid ett avbrott i internetuppkopplingen.",
        "The cloud's own word that the system reports in. Offline means the cloud has not "
        "heard from it for a while, for instance during an internet outage.",
    ),
    "last_seen": (
        "När anläggningen senast hördes av enligt molnet. Molnet uppdaterar uppgiften ungefär "
        "var femte minut, så den ligger alltid lite efter.",
        "When the system was last heard from, according to the cloud. The cloud updates it "
        "about every five minutes, so it always lags a little.",
    ),
    "battery_capacity": (
        "Batteriets märkkapacitet enligt Ferroamp, i kWh. EMS använder den för att räkna "
        "laddnivån till energi.",
        "The battery's rated capacity according to Ferroamp, in kWh. EMS uses it to turn the "
        "charge into energy.",
    ),
    "max_charge_power": (
        "Batteriets märkeffekt enligt Ferroamp, i W. Den sätter gränserna för börvärdet.",
        "The battery's rated power according to Ferroamp, in W. It sets the setpoint's range.",
    ),
}


def text(key: str, lang: str) -> str:
    """A UI string in ``lang``, Swedish when the English is missing."""
    sv, en = UI[key]
    return en if lang == ENGLISH and en else sv


def name(key: str, lang: str) -> str:
    """The page's name for ``key`` in ``lang``."""
    sv, en = NAMES[key]
    return en if lang == ENGLISH and en else sv


def explain(key: str, lang: str) -> str:
    """The explanation for ``key`` in ``lang``."""
    sv, en = EXPLAIN[key]
    return en if lang == ENGLISH and en else sv


def words(kind: str, lang: str) -> dict[str, str]:
    """The words for a kind of state, value to word, in ``lang``."""
    index = 1 if lang == ENGLISH else 0
    return {value: pair[index] for value, pair in WORDS[kind].items()}
