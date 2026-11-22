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
    "battery": ("Batteriet", "The battery"),
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
