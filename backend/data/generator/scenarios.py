"""Hand-written source of the synthetic dataset: inventory, events, conversations and ground truth."""

# --------------------------------------------------------------------------
# People (section 6)
# --------------------------------------------------------------------------
ROLES = {
    "Erkki Expert": "Network Expert",
    "Veikko Vikkelä": "Field Engineer",
    "Sanna Siirto": "Network Expert",
    "Jari Jänne": "Network Expert",
    "Mikko Mäkelä": "Field Engineer",
    "Laura Lahti": "Field Engineer",
    "Pekka Pylväs": "Field Engineer",
    "Tiina Tuominen": "NOC Operator",
    "Antti Aalto": "Network Expert",
}
ERKKI, VEIKKO, SANNA, JARI, MIKKO, LAURA, PEKKA, TIINA, ANTTI = list(ROLES)

SNAPSHOT_DATE = "2026-10-31"

# --------------------------------------------------------------------------
# Inventory: current state on SNAPSHOT_DATE (section 3.1)
# --------------------------------------------------------------------------
NODES = [
    # node_id, node_type, install_date, current firmware, location
    ("TRN-042", "transmission", "2019-05-14", "3.2.4", "Kolari"),
    ("TRN-077", "transmission", "2018-09-03", "3.4.0", "Muonio"),
    ("TRN-015", "transmission", "2017-04-21", "3.4.0", "Kittilä"),
    ("TRN-031", "transmission", "2019-08-30", "3.3.0", "Sodankylä"),
    ("TRN-101", "transmission", "2022-11-10", "5.1.0", "Oulu"),
    ("TRN-112", "transmission", "2023-06-05", "5.2.1", "Rovaniemi"),
    ("TRN-118", "transmission", "2024-02-19", "5.2.3", "Kajaani"),
    ("AGG-003", "aggregation_router", "2020-02-17", "7.3.2", "Oulu"),
    ("AGG-007", "aggregation_router", "2022-05-11", "7.4.0", "Rovaniemi"),
    ("AGG-012", "aggregation_router", "2019-03-08", "7.2.0", "Kajaani"),
    ("BTS-210", "base_station", "2018-07-25", "2.6.0", "Muonio"),
    ("BTS-233", "base_station", "2019-10-12", "2.4.1", "Kolari"),
    ("BTS-250", "base_station", "2022-09-14", "2.6.0", "Tampere"),
    ("BTS-261", "base_station", "2023-01-30", "2.6.2", "Kittilä"),
    ("MW-401", "microwave_link", "2017-06-02", "1.4.0", "Sodankylä"),
    ("MW-405", "microwave_link", "2018-01-30", "1.4.0", "Kittilä"),
    ("MW-412", "microwave_link", "2021-08-16", "1.4.0", "Rovaniemi"),
    # 8 extra devices (v4 amendment 6: firmware fits age). Several are
    # deliberately never mentioned in any conversation, so the demo can show
    # knowledge reaching a device purely through its scope rule.
    ("TRN-023", "transmission", "2018-03-12", "3.3.1", "Rovaniemi"),
    ("TRN-056", "transmission", "2016-10-05", "3.1.4", "Kemijärvi"),
    ("TRN-125", "transmission", "2025-03-03", "5.2.3", "Tampere"),
    ("AGG-015", "aggregation_router", "2023-09-20", "7.3.5", "Tampere"),
    ("BTS-205", "base_station", "2017-11-08", "2.3.4", "Kemijärvi"),
    ("BTS-244", "base_station", "2019-04-17", "2.5.0", "Pello"),
    ("BTS-272", "base_station", "2024-05-22", "2.6.2", "Oulu"),
    ("MW-418", "microwave_link", "2019-05-28", "1.4.0", "Pello"),
]

# Required firmware histories (section 3.1). validate.py checks events match.
FIRMWARE_HISTORY = {
    "TRN-077": [("3.2.1", "3.4.0", "2026-03-24")],
    "TRN-015": [("3.1.2", "3.4.0", "2026-03-25")],
    "AGG-007": [("7.3.5", "7.4.0", "2025-05-21")],
    "BTS-210": [("2.4.0", "2.6.0", "2026-02-18")],
    "MW-401": [("1.3.0", "1.4.0", "2023-10-17")],
    "MW-405": [("1.3.2", "1.4.0", "2023-10-18")],
    "MW-412": [("1.3.4", "1.4.0", "2023-10-19")],
    "MW-418": [("1.3.4", "1.4.0", "2023-10-20")],  # extra device, same wave
}

# --------------------------------------------------------------------------
# Events (section 3.2). (date, time, node, type, detail, related_thread, extra)
# IDs are assigned by build.py in time order.
# --------------------------------------------------------------------------
FW = "firmware_upgrade"
EVENTS = [
    # --- firmware upgrades -------------------------------------------------
    ("2023-10-17", "10:00", "MW-401", FW, "Planned firmware upgrade", None, {"from_firmware": "1.3.0", "to_firmware": "1.4.0"}),
    ("2023-10-18", "10:00", "MW-405", FW, "Planned firmware upgrade", None, {"from_firmware": "1.3.2", "to_firmware": "1.4.0"}),
    ("2023-10-19", "10:30", "MW-412", FW, "Planned firmware upgrade", None, {"from_firmware": "1.3.4", "to_firmware": "1.4.0"}),
    ("2023-10-20", "09:30", "MW-418", FW, "Planned firmware upgrade", None, {"from_firmware": "1.3.4", "to_firmware": "1.4.0"}),
    ("2025-05-21", "23:30", "AGG-007", FW, "Maintenance window firmware upgrade", "T005", {"from_firmware": "7.3.5", "to_firmware": "7.4.0"}),
    ("2026-02-18", "10:00", "BTS-210", FW, "Planned firmware upgrade", "T016", {"from_firmware": "2.4.0", "to_firmware": "2.6.0"}),
    ("2026-03-24", "10:00", "TRN-077", FW, "Planned firmware upgrade", "E007", {"from_firmware": "3.2.1", "to_firmware": "3.4.0"}),
    ("2026-03-25", "10:00", "TRN-015", FW, "Planned firmware upgrade", "E007", {"from_firmware": "3.1.2", "to_firmware": "3.4.0"}),
    # --- T013 (no device id in chat; event links the session) -------------
    # --- E003: microwave fading after 1.4 upgrade --------------------------
    ("2023-10-27", "16:20", "MW-412", "alarm_raised", "Link degradation: RSL below threshold during rain", "E003", {}),
    ("2023-10-27", "17:05", "MW-412", "alarm_cleared", "Link degradation cleared", "E003", {}),
    # --- T003 / T017: MW-405 -------------------------------------------------
    ("2024-01-18", "06:30", "MW-405", "alarm_raised", "Radio link unstable: repeated link down/up", "T003", {}),
    ("2024-01-18", "07:15", "MW-405", "dispatch", "Field engineer dispatched to Kittilä mast", "T003", {}),
    ("2024-01-18", "10:38", "MW-405", "alarm_cleared", "Radio link stable", "T003", {}),
    ("2024-01-25", "19:50", "MW-405", "alarm_raised", "Radio link down", "T017", {}),
    # --- T010: AGG-003 CPU --------------------------------------------------
    ("2024-03-19", "02:00", "AGG-003", "alarm_raised", "CPU utilisation 88%", "T010", {}),
    ("2024-03-19", "02:14", "AGG-003", "alarm_cleared", "CPU utilisation normal", "T010", {}),
    # --- E005: third-party SFPs -----------------------------------------------
    ("2024-05-02", "11:40", "TRN-056", "alarm_raised", "Port 1/1/2: unsupported transceiver, port down", "E005", {}),
    ("2024-05-03", "13:10", "TRN-023", "alarm_raised", "Port 1/1/4: unsupported transceiver, port down", "E005", {}),
    # --- T004: BTS-233 power outage ------------------------------------------
    ("2024-06-03", "05:40", "BTS-233", "alarm_raised", "Mains power failure", "T004", {}),
    ("2024-06-03", "05:41", "BTS-233", "alarm_raised", "Cell out of service", "T004", {}),
    ("2024-06-03", "07:00", "BTS-233", "dispatch", "Field engineer dispatched, cell down after power outage", "T004", {}),
    ("2024-06-03", "08:44", "BTS-233", "alarm_cleared", "Cell in service", "T004", {}),
    # --- T007: TRN-015 fan alarm ---------------------------------------------
    ("2024-08-14", "11:02", "TRN-015", "alarm_raised", "Fan failure", "T007", {}),
    # --- T008: MW-412 storm ----------------------------------------------------
    ("2024-10-01", "22:10", "MW-412", "alarm_raised", "Radio link down, RSL -78 dBm", "T008", {}),
    ("2024-10-02", "07:00", "MW-412", "dispatch", "Field engineer dispatched after storm", "T008", {}),
    ("2024-10-02", "10:25", "MW-412", "alarm_cleared", "Radio link up, RSL normal", "T008", {}),
    # --- E002 / E008 ---------------------------------------------------------
    ("2024-11-19", "09:00", "TRN-042", "dispatch", "Dispatch delayed 2 h: locked barrier on private access road", "E008", {}),
    ("2024-11-19", "14:30", "AGG-012", "work_order", "WO-48817: Re-cable uplink patch panel, rack 2", "E002", {}),
    ("2024-11-19", "16:05", "AGG-012", "alarm_raised", "CRC errors on uplink port", "E002", {}),
    ("2024-11-20", "10:40", "AGG-012", "alarm_cleared", "CRC errors on uplink port cleared", "E002", {}),
    # --- T006: BTS-250 battery ------------------------------------------------
    ("2025-01-09", "06:10", "BTS-250", "alarm_raised", "Battery alarm", "T006", {}),
    # --- T012: AGG-003 CRC -----------------------------------------------------
    ("2025-01-27", "13:00", "AGG-003", "work_order", "WO-52031: Rack maintenance, re-patching", "T012", {}),
    ("2025-01-28", "08:10", "AGG-003", "alarm_raised", "CRC errors on uplink port", "T012", {}),
    ("2025-01-28", "08:41", "AGG-003", "alarm_cleared", "CRC errors on uplink port cleared", "T012", {}),
    # --- T011: BTS-261 GPS ------------------------------------------------------
    ("2025-02-03", "04:30", "BTS-261", "alarm_raised", "GPS synchronisation lost", "T011", {}),
    ("2025-02-03", "07:30", "BTS-261", "dispatch", "Field engineer dispatched, GPS sync lost", "T011", {}),
    ("2025-02-03", "10:51", "BTS-261", "alarm_cleared", "GPS synchronisation restored", "T011", {}),
    # --- E004: TRN-101 hot swap -----------------------------------------------
    ("2025-02-27", "09:00", "TRN-101", "work_order", "WO-53390: Replace line module slot 3", "E004", {}),
    ("2025-02-27", "10:12", "TRN-101", "hw_replacement", "Line module slot 3 hot-swapped", "E004", {}),
    ("2025-02-27", "10:13", "TRN-101", "alarm_raised", "Unknown module in slot 3", "E004", {}),
    ("2025-02-27", "10:16", "TRN-101", "alarm_cleared", "Unknown module in slot 3 cleared", "E004", {}),
    # --- T001 / E001: Elisa's case ---------------------------------------------
    ("2025-03-12", "07:58", "TRN-042", "alarm_raised", "LOS on port 1/1/3", "T001", {}),
    ("2025-03-12", "08:40", "TRN-042", "work_order", "WO-55120: Replace SFP on port 1/1/3, reason: LOS alarm", "T001", {}),
    ("2025-03-12", "09:05", "TRN-042", "alarm_cleared", "LOS on port 1/1/3 cleared", "T001", {}),
    # --- T021: BTS-210 routine ---------------------------------------------------
    ("2025-04-16", "08:00", "BTS-210", "work_order", "WO-56102: Routine battery check", "T021", {}),
    # --- T005: AGG-007 LACP --------------------------------------------------------
    ("2025-05-21", "23:50", "AGG-007", "alarm_raised", "LACP bundle to core down", "T005", {}),
    ("2025-05-22", "08:26", "AGG-007", "alarm_cleared", "LACP bundle to core up", "T005", {}),
    # --- T014: TRN-015 wrong advice (reboot) -----------------------------------
    ("2025-06-30", "08:05", "TRN-015", "alarm_raised", "LOS on port 1/1/1", "T014", {}),
    ("2025-06-30", "09:30", "TRN-015", "hw_replacement", "SFP replaced on port 1/1/1", "T014", {}),
    ("2025-06-30", "09:46", "TRN-015", "alarm_raised", "Node unreachable", "T014", {}),
    ("2025-06-30", "10:06", "TRN-015", "alarm_cleared", "Node reachable", "T014", {}),
    # --- T015: TRN-031 wrong advice (SFP again) ---------------------------------
    ("2025-07-15", "07:40", "TRN-031", "alarm_raised", "LOS on port 1/1/2", "T015", {}),
    ("2025-07-15", "11:05", "TRN-031", "hw_replacement", "SFP replaced on port 1/1/2", "T015", {}),
    ("2025-07-15", "11:38", "TRN-031", "hw_replacement", "SFP replaced again on port 1/1/2", "T015", {}),
    # --- T018: AGG-012 LACP -----------------------------------------------------
    ("2025-08-11", "09:12", "AGG-012", "alarm_raised", "LACP bundle to core down", "T018", {}),
    # --- T002: TRN-077 reinforcing ----------------------------------------------
    ("2025-09-04", "07:20", "TRN-077", "alarm_raised", "LOS on port 1/1/2", "T002", {}),
    ("2025-09-04", "07:45", "TRN-077", "work_order", "WO-58873: Replace SFP on port 1/1/2, reason: LOS alarm", "T002", {}),
    ("2025-09-04", "10:02", "TRN-077", "alarm_cleared", "LOS on port 1/1/2 cleared", "T002", {}),
    # --- C002: MW-401 speculation -------------------------------------------------
    ("2025-09-20", "17:30", "MW-401", "alarm_raised", "Errored seconds above threshold", "C002", {}),
    # --- T009: TRN-112 dirty connector --------------------------------------------
    ("2025-11-04", "09:00", "TRN-112", "work_order", "WO-60214: Planned maintenance, fibre re-patching", "T009", {}),
    ("2025-11-05", "08:30", "TRN-112", "alarm_raised", "Low RX optical power on port 1/1/2", "T009", {}),
    ("2025-11-05", "10:04", "TRN-112", "alarm_cleared", "Low RX optical power on port 1/1/2 cleared", "T009", {}),
    # --- C001: BTS-210 night outage -----------------------------------------------
    ("2025-12-10", "00:55", "BTS-210", "alarm_raised", "Mains power failure", "C001", {}),
    ("2025-12-10", "01:00", "BTS-210", "alarm_raised", "Cell out of service", "C001", {}),
    ("2025-12-10", "01:20", "BTS-210", "dispatch", "On-call field engineer dispatched", "C001", {}),
    # --- E006: TRN-031 bounce fix -----------------------------------------------------
    ("2026-02-13", "08:15", "TRN-031", "alarm_raised", "LOS on port 1/1/2", "E006", {}),
    ("2026-02-13", "11:20", "TRN-031", "hw_replacement", "SFP replaced on port 1/1/2", "E006", {}),
    # --- T016: BTS-210 recovers by itself on 2.6 ---------------------------------------
    ("2026-03-01", "23:10", "BTS-210", "alarm_raised", "Mains power failure", "T016", {}),
    ("2026-03-01", "23:24", "BTS-210", "alarm_cleared", "Cell in service", "T016", {}),
    # --- E007: SFP swaps on 3.4 without issue -------------------------------------------
    ("2026-03-31", "10:40", "TRN-077", "hw_replacement", "SFP replaced on port 1/1/1", "E007", {}),
    ("2026-04-02", "13:15", "TRN-015", "hw_replacement", "SFP replaced on port 1/1/3", "E007", {}),
    # --- background, unrelated to any conversation ----------------------------------------
    ("2023-08-22", "14:10", "TRN-056", "alarm_raised", "High temperature", None, {}),
    ("2023-08-22", "15:30", "TRN-056", "alarm_cleared", "High temperature cleared", None, {}),
    ("2024-04-11", "09:20", "TRN-118", "alarm_raised", "LOS on port 1/1/4", None, {}),
    ("2024-04-11", "12:45", "TRN-118", "alarm_cleared", "LOS on port 1/1/4 cleared", None, {}),
    ("2024-09-09", "08:00", "BTS-272", "work_order", "WO-46551: Antenna tilt adjustment", None, {}),
    ("2025-06-12", "13:40", "AGG-015", "alarm_raised", "Power supply 2 failure", None, {}),
    ("2025-06-13", "10:10", "AGG-015", "hw_replacement", "Power supply 2 replaced", None, {}),
    ("2025-10-07", "07:55", "BTS-244", "alarm_raised", "Door open alarm", None, {}),
    ("2026-01-15", "04:20", "BTS-205", "alarm_raised", "Mains power failure", None, {}),
    ("2026-01-15", "06:05", "BTS-205", "alarm_cleared", "Mains power restored", None, {}),
    ("2026-05-19", "09:30", "TRN-125", "work_order", "WO-63380: Add 10G interface", None, {}),
]

# --------------------------------------------------------------------------
# Threads (section 7). Teams/call: messages = [(HH:MM, author, text)].
# Email: one message; date+time, sender, to, subject, body.
# T001 and E001 are loaded word for word from Elisa's files by build.py.
# --------------------------------------------------------------------------
THREADS = [
    # ================= 7.1 correct technical knowledge =====================
    dict(id="T001", channel="teams", date="2025-03-12", language="en", elisa_original=True),
    dict(id="E001", channel="email", date="2025-03-12", time="14:02", language="en", elisa_original=True,
         sender=ERKKI, to=[VEIKKO]),

    dict(id="T002", channel="teams", date="2025-09-04", language="fi", participants=[PEKKA, ERKKI], messages=[
        ("10:05", PEKKA, "Moi Erkki, oon Muoniossa TRN-077:llä. Vaihdoin SFP:n, linkki on ylhäällä ja hälyt poissa mut liikenne ei kulje 🤔"),
        ("10:07", ERKKI, "Moi. Onko tää niitä vanhoja laitteita?"),
        ("10:07", PEKKA, "Joo, 2018 asennettu jos muistan oikein"),
        ("10:08", ERKKI, "Katso kasvaako liikennelaskurit. Jos ne on nollassa vaikka portti on ylhäällä, niin se on sama juttu kuin Kolarissa keväällä"),
        ("10:10", PEKKA, "Laskurit nollassa joo. RX taso ok"),
        ("10:11", PEKKA, "Laitanko vielä uuden SFP:n?"),
        ("10:11", ERKKI, "Ei tarvii. Ota portti alas, odota hetki ja nosta takaisin. Älä buuttaa koko laitetta"),
        ("10:14", PEKKA, "Done. Liikenne kulkee taas 👍"),
        ("10:15", ERKKI, "Hyvä. Noissa vanhoissa forwarding jää välillä jumiin optiikan vaihdon jälkeen"),
        ("10:15", PEKKA, "Ok, laitan korvan taakse 😅"),
    ]),

    dict(id="E006", channel="email", date="2026-02-16", time="10:20", language="fi", sender=ERKKI, to=[MIKKO],
         subject="RE: TRN-031 Sodankylä, liikenne ei palannut",
         body="""Moi Mikko,

Kävin perjantaina TRN-031:llä Sodankylässä. Sama tilanne kuin aiemmin: SFP vaihdettu, portti ylhäällä, optiset tasot normaalit, mutta liikennelaskurit nollassa.

Portin disablointi ja enablointi korjasi tilanteen heti. SFP:tä ei tarvinnut vaihtaa eikä laitetta buutata.

Sama juttu on nähty nyt TRN-042:lla ja TRN-077:llä. Näissä vanhemmissa siirtolaitteissa kannattaa aina ensin katsoa laskurit ja kokeilla portin sammutusta ja käynnistystä ennen kuin vaihtaa rautaa.

Terveisin,
Erkki
"""),

    dict(id="E002", channel="email", date="2024-11-20", time="13:30", language="en", sender=ANTTI, to=[LAURA],
         subject="RE: AGG-012 uplink CRC errors after cable work",
         body="""Hi Laura,

Good to hear the cable swap fixed it this morning. Errors have stayed at zero here too since about 10:40.

On these routers it's almost always the patch cable when CRC errors start right after cable work. Before anyone orders a new line card, swap the patch cable on the uplink first.

I've seen the same on several aggregation routers, old and new, so worth checking the cable every time.

Br,
Antti
"""),

    dict(id="T012", channel="teams", date="2025-01-28", language="mixed", participants=[LAURA, ANTTI], messages=[
        ("08:25", LAURA, "Moi Antti, AGG-003 Oulussa: CRC errors on the uplink since this morning. There was maintenance here yesterday"),
        ("08:27", ANTTI, "Did they touch the cables?"),
        ("08:28", LAURA, "Joo, they re-patched the whole rack"),
        ("08:29", ANTTI, "Same as Kajaani last autumn then. Vaihda patch-kaapeli ensin, don't touch the line card yet"),
        ("08:41", LAURA, "Swapped the cable. Errors stopped 👍"),
        ("08:42", ANTTI, "Nice. Almost always the cable on these"),
    ]),

    dict(id="T004", channel="teams", date="2024-06-03", language="en", participants=[VEIKKO, SANNA], messages=[
        ("08:30", VEIKKO, "Sanna, BTS-233 in Kolari. Power came back around 6 but the cell is still down. Rebooted it once already, no change"),
        ("08:32", SANNA, "Normal reboot from the menu?"),
        ("08:32", VEIKKO, "Yes"),
        ("08:33", SANNA, "That doesn't help on these older base stations. The baseband doesn't come up properly after a power cut"),
        ("08:34", SANNA, "Do a cold restart of the baseband unit. Power it off completely, wait 30 sec, power on"),
        ("08:35", VEIKKO, "Ok trying"),
        ("08:44", VEIKKO, "Cell is up 👍"),
        ("08:45", SANNA, "Good. Always the cold restart on the old ones after an outage, the warm reboot is just wasted time"),
    ]),

    dict(id="C001", channel="call", date="2025-12-10", language="fi", participants=[PEKKA, SANNA], messages=[
        ("02:40", PEKKA, "Joo moi Sanna, sori että soitan tähän aikaan. Eli Muoniossa BTS-210, oli sähkökatko ja nyt solu ei nouse."),
        ("02:40", SANNA, "Joo joo, ei se mitään. Ootko jo buutannut sen?"),
        ("02:41", PEKKA, "En vielä, olin just tekemässä rebootin sieltä valikosta."),
        ("02:41", SANNA, "Älä tee sitä. Eli noissa vanhoissa tukiasemissa tavallinen reboot ei auta. Tee baseband-yksikölle kylmäkäynnistys, virrat kokonaan pois, odota puoli minuuttia ja takaisin päälle."),
        ("02:42", PEKKA, "Okei, eli virrat pois siitä baseband-yksiköstä... joo, hetki."),
        ("02:47", PEKKA, "Noni, nyt näyttää hyvältä. Joo, solu on ylhäällä."),
        ("02:47", SANNA, "Hyvä. Sama juttu oli Kolarissa viime kesänä, se toimii aina noissa vanhoissa."),
        ("02:48", PEKKA, "Okei cool, kiitti. Hyvää yötä!"),
    ]),

    dict(id="T003", channel="teams", date="2024-01-18", language="fi", participants=[PEKKA, ERKKI], messages=[
        ("10:10", PEKKA, "Moi Erkki, MW-405 Kittilässä pätkii taas. Lunta tullu koko yön"),
        ("10:12", ERKKI, "Ootko jo paikan päällä?"),
        ("10:12", PEKKA, "Joo, mastolla nyt"),
        ("10:13", ERKKI, "Katso ensin onko antennin suojakuvussa jäätä. Älä koske radioon ennen sitä"),
        ("10:20", PEKKA, "Joo, paksu jääkerros radomin päällä 🥶"),
        ("10:21", ERKKI, "Putsaa se pois. Jää syö signaalin, radio on yleensä ihan ok"),
        ("10:38", PEKKA, "Putsattu. Linkki pysyy nyt ylhäällä 👍"),
        ("10:39", ERKKI, "Hyvä. Talvella aina eka radomi"),
    ]),

    dict(id="T005", channel="teams", date="2025-05-22", language="en", participants=[VEIKKO, ANTTI], messages=[
        ("08:15", VEIKKO, "Antti, AGG-007 Rovaniemi. Firmware was upgraded to 7.4 last night and the LACP bundle to the core is still down this morning"),
        ("08:17", ANTTI, "Physical links up?"),
        ("08:17", VEIKKO, "Yes, both members up, optics fine. Bundle just won't form"),
        ("08:19", ANTTI, "Known thing with 7.4. Remove the member ports from the port-channel config and add them back. The upgrade leaves them in a weird state"),
        ("08:20", VEIKKO, "No reboot needed?"),
        ("08:20", ANTTI, "No, just the config"),
        ("08:26", VEIKKO, "Done, bundle is up and passing traffic 👍"),
        ("08:27", ANTTI, "Good. Probably the same on the other routers when they get 7.4"),
    ]),

    dict(id="E003", channel="email", date="2023-10-30", time="10:05", language="en", sender=JARI, to=[ERKKI],
         subject="ATPC off after the 1.4 upgrade",
         body="""Hi Erkki,

Heads-up on the microwave links. The 1.4 firmware upgrade we did a couple of weeks ago on MW-401, MW-405 and MW-412 reset the ATPC setting to off on all of them.

Nobody noticed in good weather, but with the rain on Friday MW-412 started fading badly. I turned ATPC back on and the link has been stable since. Checked the other two and switched it back on there as well.

So: after every firmware upgrade on these links, check that ATPC is still enabled. It's not in the upgrade checklist yet.

Cheers,
Jari
"""),

    dict(id="T006", channel="teams", date="2025-01-09", language="fi", participants=[TIINA, SANNA], messages=[
        ("07:20", TIINA, "Moi Sanna, BTS-250 Tampereella antaa akkuhälytystä. Pitäiskö lähettää joku paikalle?"),
        ("07:22", SANNA, "Oliko siellä yöllä kova pakkanen?"),
        ("07:22", TIINA, "-28 astetta aamulla"),
        ("07:24", SANNA, "Se on todennäköisesti väärä hälytys. Katso tasasuuntaajan lämpötila-anturin lukema ennen kuin lähetät ketään"),
        ("07:29", TIINA, "Anturi näyttää -40, ihan mahdoton arvo. Akkujännite normaali"),
        ("07:30", SANNA, "Joo, anturi sekoaa kovalla pakkasella. Ei tarvii käydä, hälytys poistuu kun lämpenee"),
        ("07:31", TIINA, "Hyvä, säästettiin yks reissu 👍"),
    ]),

    dict(id="T007", channel="teams", date="2024-08-14", language="en", participants=[TIINA, ERKKI], messages=[
        ("11:15", TIINA, "Erkki, fan alarm on TRN-015 in Kittilä. Do I need to send someone?"),
        ("11:17", ERKKI, "What's the chassis temp?"),
        ("11:18", TIINA, "38 C, normal range"),
        ("11:19", ERKKI, "Then no. That's the fan sensor bug in the 3.1 software, false alarm. Only dispatch if the chassis temp goes up"),
        ("11:19", TIINA, "Ok, closing it 👍"),
    ]),

    dict(id="E004", channel="email", date="2025-02-27", time="15:20", language="mixed", sender=ERKKI, to=[LAURA],
         subject="RE: TRN-101 unknown module after swap",
         body="""Moi Laura,

That's normal on the transmission nodes, ei hätää. After a hot swap the new line module shows as "unknown module" until the inventory refresh runs, se kestää noin 3 minuuttia.

So wait ~3 min before you reseat or replace anything. Jos se on vielä unknown viiden minuutin jälkeen, then reseat it once.

Hyvä että se nousi lopulta itsestään.

Terveisin,
Erkki
"""),

    dict(id="T008", channel="teams", date="2024-10-02", language="en", participants=[VEIKKO, JARI], messages=[
        ("09:40", VEIKKO, "Jari, MW-412 lost alignment in last night's storm. Signal way down. Should I bring a new radio?"),
        ("09:42", JARI, "No. Check the mount bolts first. Storm usually just loosens the mount"),
        ("09:50", VEIKKO, "Two bolts loose on the pole mount, dish turned a bit"),
        ("09:51", JARI, "Tighten them and re-align. Radio is fine"),
        ("10:25", VEIKKO, "Re-aligned, levels back to normal 👍"),
        ("10:26", JARI, "Good. Never seen the radio die from wind on these"),
    ]),

    dict(id="T009", channel="teams", date="2025-11-05", language="en", participants=[VEIKKO, ERKKI], messages=[
        ("09:50", VEIKKO, "Erkki, TRN-112 after yesterday's maintenance: RX level low on 1/1/2, about 6 dB worse than before. Swap the SFP?"),
        ("09:52", ERKKI, "Did they unplug the fibre during the work?"),
        ("09:52", VEIKKO, "Yes, they moved patches around"),
        ("09:53", ERKKI, "Clean the connector first. Click-cleaner on both ends. A dirty connector is way more common than a bad SFP"),
        ("10:04", VEIKKO, "Cleaned both. RX back to normal 👍"),
        ("10:05", ERKKI, "There you go. Don't throw away good SFPs 😄"),
    ]),

    dict(id="T010", channel="teams", date="2024-03-19", language="en", participants=[TIINA, ANTTI], messages=[
        ("08:20", TIINA, "Antti, AGG-003 had a CPU spike at 02:00 again, 88%. Third night this week. Anything to worry about?"),
        ("08:23", ANTTI, "How long did it last?"),
        ("08:23", TIINA, "About 14 min"),
        ("08:25", ANTTI, "That's the nightly config backup job. Normal on these. Ignore it unless it goes over 95% for more than 10 minutes"),
        ("08:25", TIINA, "Ok, I'll put that in the shift log 👍"),
    ]),

    dict(id="T011", channel="teams", date="2025-02-03", language="fi", participants=[PEKKA, SANNA], messages=[
        ("10:30", PEKKA, "Moi Sanna, BTS-261 menetti GPS-synkan yöllä. Lunta tuli paljon. Antenni näyttää ehjältä"),
        ("10:32", SANNA, "Tarkista GPS-antennin lämmittimen sulake. Lumi ja jää kertyy kupuun jos lämmitin ei toimi"),
        ("10:38", PEKKA, "Sulake palanut 🔥"),
        ("10:39", SANNA, "Vaihda se, synkka palaa yleensä parissa minuutissa"),
        ("10:51", PEKKA, "Uus sulake, sync ok taas 👍"),
        ("10:52", SANNA, "Hyvä 👌"),
    ]),

    dict(id="E005", channel="email", date="2024-05-07", time="09:40", language="en", sender=ERKKI, to=[ANTTI],
         subject="Third-party SFPs on the old transmission nodes",
         body="""Hi Antti,

FYI since your team shares the spare stock with us. The older transmission nodes refuse the third-party SFPs from the latest spare batch. The port just says the module is not supported and stays down.

We wasted two site visits on this last week. Only use the approved part, SFP-10G-LR-02. The newer transmission nodes accept both.

I asked logistics to label the shelf.

Regards,
Erkki
"""),

    dict(id="T013", channel="teams", date="2023-06-12", language="en", participants=[MIKKO, ERKKI], messages=[
        ("08:30", MIKKO, "Erkki, I'm at one of the old transmission boxes, console cable connected but I only get garbage on the screen"),
        ("08:31", ERKKI, "What speed are you using?"),
        ("08:31", MIKKO, "115200 like on the new ones"),
        ("08:32", ERKKI, "The old ones run at 9600. Change it"),
        ("08:33", MIKKO, "Works now, thanks 😅"),
        ("08:33", ERKKI, "All the older transmission nodes are 9600, only the new ones are 115200"),
    ]),

    # ================= 7.2 wrong / outdated / conflicting / noise ============
    dict(id="T014", channel="teams", date="2025-06-30", language="en", participants=[PEKKA, MIKKO], messages=[
        ("09:40", PEKKA, "Mikko, TRN-015 Kittilä. Swapped the SFP, link is up, no alarms, but no traffic. Erkki is on holiday, any ideas?"),
        ("09:42", MIKKO, "Just reboot the unit, that usually sorts it out"),
        ("09:43", PEKKA, "The whole node? That takes everything down"),
        ("09:43", MIKKO, "Yeah takes maybe 20 min but it resets everything"),
        ("09:45", PEKKA, "Ok rebooting"),
        ("10:08", PEKKA, "Back up after 20 min. Counters still zero on that port 😩 and NOC is asking why the whole site dropped"),
        ("10:10", MIKKO, "Hmm, so that didn't help. No idea then, sorry. Maybe wait for Erkki"),
    ]),

    dict(id="T015", channel="teams", date="2025-07-15", language="en", participants=[VEIKKO, TIINA], messages=[
        ("11:20", VEIKKO, "Tiina, TRN-031 Sodankylä. New SFP in, port is up and optics ok, but still no traffic"),
        ("11:22", TIINA, "Then that SFP is probably bad too, we've had bad ones lately. Put in another one"),
        ("11:23", VEIKKO, "I have one more in the car"),
        ("11:41", VEIKKO, "Second SFP in. Same thing, port up but counters at zero"),
        ("11:43", TIINA, "Weird. I'll open a ticket for the transmission team"),
        ("11:44", VEIKKO, "Ok. Heading to the next site, will come back tomorrow"),
    ]),

    dict(id="T018", channel="teams", date="2025-08-11", language="en", participants=[LAURA, ANTTI], messages=[
        ("09:20", LAURA, "Antti, AGG-012 Kajaani, LACP bundle to the core is down. Both member links are up"),
        ("09:22", ANTTI, "Remove the member ports from the port-channel and add them back. Fixed the same thing on AGG-007"),
        ("09:31", LAURA, "Done that twice. Still down"),
        ("09:33", ANTTI, "What software is it on?"),
        ("09:34", LAURA, "7.2.0"),
        ("09:35", ANTTI, "Ah sorry, that's only for the new ones after the 7.4 upgrade. Different problem then. Can you send me the logs"),
        ("09:36", LAURA, "Sending 👍"),
    ]),

    dict(id="E007", channel="email", date="2026-04-08", time="10:15", language="en", sender=ERKKI, to=[VEIKKO, PEKKA],
         subject="Traffic stuck after SFP swap: fixed in 3.4",
         body="""Hi both,

Good news on the old transmission nodes. TRN-077 and TRN-015 were upgraded to firmware 3.4 last month, and since then we have replaced SFPs on both without the traffic getting stuck. The release notes also mention a fix for the forwarding state after optics changes.

So the interface disable/enable trick is only needed on the older units that are still below 3.4. On 3.4 you can skip it; if traffic doesn't recover there, it's something else.

TRN-042 and TRN-031 are still on the old software, so keep doing the disable/enable there until they get upgraded.

Regards,
Erkki
"""),

    dict(id="T016", channel="teams", date="2026-03-02", language="en", participants=[VEIKKO, SANNA], messages=[
        ("13:10", VEIKKO, "Sanna, power cut in Muonio last night. BTS-210 came back by itself, didn't need the cold restart this time"),
        ("13:12", SANNA, "Yes! It was upgraded to 2.6 last month. 2.6 fixes the baseband not recovering after a power outage"),
        ("13:13", VEIKKO, "So no more cold restarts?"),
        ("13:14", SANNA, "Only on the old ones still below 2.6. BTS-233 in Kolari is still on the old software, there you still need the cold restart"),
        ("13:15", VEIKKO, "Ok good to know 👍"),
    ]),

    dict(id="T017", channel="teams", date="2024-01-25", language="fi", participants=[PEKKA, JARI], messages=[
        ("21:40", PEKKA, "Jari, MW-405 putoo taas. Pakkasta -32. Putsasin radomin viime viikolla, nyt ei oo jäätä"),
        ("21:43", JARI, "Ei se oo jää. Noissa ulkoyksiköissä virtalähde sakkaa kovalla pakkasella"),
        ("21:44", PEKKA, "Erkki sano viime viikolla että se on jää"),
        ("21:46", JARI, "Ehkä, mut veikkaan että se oli virtalähde silloinkin. Vaihda PSU niin näet"),
        ("21:47", PEKKA, "Ok, mulla ei oo varaosaa autossa. Huomenna"),
        ("21:48", JARI, "Joo, tilaa uus PSU"),
    ]),

    dict(id="T019", channel="teams", date="2024-12-05", language="mixed", participants=[TIINA, PEKKA, LAURA, VEIKKO], messages=[
        ("11:30", TIINA, "Pikkujoulut 13.12! Rovaniemi again, who is in? 🎄"),
        ("11:32", PEKKA, "Mä tuun. Unless AGG-007 decides to die that evening 😅"),
        ("11:33", LAURA, "Joo mukana. Can someone book the sauna?"),
        ("11:35", VEIKKO, "I'll drive from Kolari, have space for 2"),
        ("11:36", TIINA, "Hyvä, I'll book a table for 12"),
    ]),

    dict(id="T020", channel="teams", date="2025-03-03", language="fi", participants=[VEIKKO, PEKKA, TIINA], messages=[
        ("14:05", VEIKKO, "Moi, voisko joku vaihtaa päivystysvuoron 15.3? Mulla on häät"),
        ("14:08", PEKKA, "Mä voin ottaa sen jos sä otat mun 22.3"),
        ("14:09", VEIKKO, "Diili 👍"),
        ("14:11", TIINA, "Päivitän päivystyslistan. Muistakaa merkata tunnit järjestelmään"),
        ("14:12", PEKKA, "Joo joo 😄"),
    ]),

    dict(id="T021", channel="teams", date="2025-04-16", language="en", participants=[PEKKA, TIINA], messages=[
        ("14:40", PEKKA, "All done at BTS-210, heading back"),
        ("14:41", TIINA, "ok thanks"),
        ("14:41", PEKKA, "Road is icy, back around 16"),
        ("14:42", TIINA, "👍 drive safe"),
    ]),

    dict(id="C002", channel="call", date="2025-09-22", language="en", participants=[VEIKKO, JARI], messages=[
        ("13:05", VEIKKO, "Hey Jari, yeah, quick one. MW-401 in Sodankylä is showing some errors since the weekend, not down though."),
        ("13:05", JARI, "Okay so... errors how, like constant or in bursts?"),
        ("13:06", VEIKKO, "Bursts I think. I haven't been out there yet."),
        ("13:06", JARI, "Hmm. Could be the fibre to the indoor unit maybe? I don't know, never seen that on that link."),
        ("13:07", VEIKKO, "Yeah, or the weather? It rained a lot."),
        ("13:07", JARI, "Maybe, maybe. Hard to say without looking. Let's see if it gets worse."),
        ("13:08", VEIKKO, "Okay, yeah. I'll keep an eye on it."),
    ]),

    # ================= 7.3 access information ===================================
    dict(id="E008", channel="email", date="2024-11-20", time="16:05", language="en", sender=TIINA, to=[VEIKKO],
         subject="Access to TRN-042 / BTS-233 near Kolari: locked barrier",
         body="""Hi Veikko,

Before you head out tomorrow: the private road up to the TRN-042 / BTS-233 site near Kolari has a locked barrier at the start. Yesterday's dispatch got stuck there for two hours.

The key is in a lockbox at the neighbouring farm (the red house right before the barrier). Lockbox code is 2580. Please put the key back after.

This isn't in the site records, so I'm sending it to you directly.

Br,
Tiina
"""),

    dict(id="T022", channel="teams", date="2024-06-03", language="fi", participants=[LAURA, PEKKA], messages=[
        ("15:20", LAURA, "Moi Pekka, meen huomenna BTS-210:lle Muonioon. Tiedätsä portin koodin?"),
        ("15:22", PEKKA, "Joo, aidan portin koodi on 4471"),
        ("15:22", PEKKA, "Ja se riippulukko jumittaa, nosta porttia vähän ylöspäin niin se aukeaa"),
        ("15:23", LAURA, "Kiitos! 🙏"),
        ("15:24", PEKKA, "Eikä tota oo missään järjestelmässä 😅"),
    ]),

    dict(id="T023", channel="teams", date="2025-10-20", language="en", participants=[TIINA, PEKKA, LAURA], messages=[
        ("09:05", TIINA, "Heads up: the gate code at BTS-210 in Muonio has changed. New code is 9035, the old one doesn't work anymore"),
        ("09:07", PEKKA, "Ok thanks. Is the padlock still the sticky one?"),
        ("09:08", TIINA, "Yes, same padlock, you still need to lift the gate a bit 🙄"),
        ("09:08", LAURA, "Noted 👍"),
    ]),
]

# --------------------------------------------------------------------------
# Ground truth (section 8). For chats `valid_from_seq` points at the message
# whose timestamp is valid_from; for emails valid_from = the Date header.
# --------------------------------------------------------------------------
OLDER = "2020-01-01"


def scope(node_type, installed_before=None, firmware_below=None, firmware_at_least=None):
    return {"node_type": node_type, "installed_before": installed_before,
            "firmware_below": firmware_below, "firmware_at_least": firmware_at_least}


BOUNCE_SUMMARY = ("On older transmission nodes, after SFP replacement the interface can be UP with normal optics "
                  "but zero traffic; this is a forwarding-state issue, fixed by disabling and re-enabling the interface.")
BOUNCE_COMMON = dict(knowledge_type="troubleshooting_rule", summary=BOUNCE_SUMMARY,
                     events=["SFP_REPLACEMENT"],
                     symptoms=["INTERFACE_UP", "OPTICAL_LEVELS_NORMAL", "ALARMS_CLEARED", "TRAFFIC_COUNTERS_ZERO"],
                     actions=["CHECK_TRAFFIC_COUNTERS", "BOUNCE_INTERFACE"],
                     avoid=["REPLACE_SFP", "REBOOT_UNIT"], outcome="worked", details=None)
COLD_SUMMARY = ("On older base stations the cell can stay down after a power outage; a normal (warm) reboot does not "
                "help, a cold restart of the baseband unit does.")
COLD_COMMON = dict(knowledge_type="troubleshooting_rule", summary=COLD_SUMMARY,
                   events=["POWER_OUTAGE"], symptoms=["CELL_DOWN"],
                   actions=["COLD_RESTART_BASEBAND"], avoid=["WARM_REBOOT"], outcome="worked", details=None)
CABLE_SUMMARY = ("On aggregation routers, CRC errors on an uplink right after cable work are almost always caused by "
                 "the patch cable; replace the patch cable before replacing the line card.")


def merge(target, source, add_observed_on=None):
    eff = {"target": target, "action": "merge", "add_source": source}
    if add_observed_on:
        eff["add_observed_on"] = add_observed_on
    return [eff]


GROUND_TRUTH = {
    # ---- 7.1 -------------------------------------------------------------
    "T001": dict(category="correct_fix", knowledge=dict(
        BOUNCE_COMMON, observed_on=["TRN-042"], scope=scope("transmission", OLDER),
        author=ERKKI, source_message_seqs=[6, 8, 9, 10], valid_from_seq=9),
        relations=[], expected_effects=[], notes="Elisa's original example, copied word for word."),
    "E001": dict(category="correct_fix", knowledge=dict(
        BOUNCE_COMMON, observed_on=["TRN-042"], scope=scope("transmission", OLDER),
        author=ERKKI, source_message_seqs=[1]),
        relations=[{"type": "same_knowledge_as", "target": "T001"}],
        expected_effects=merge("T001", "E001"),
        notes="Elisa's original email, copied word for word. Same knowledge as T001, second source."),
    "T002": dict(category="reinforcing", knowledge=dict(
        BOUNCE_COMMON, observed_on=["TRN-077"], scope=scope("transmission", OLDER),
        author=ERKKI, source_message_seqs=[4, 7, 8, 9], valid_from_seq=8),
        relations=[{"type": "reinforces", "target": "T001"}],
        expected_effects=merge("T001", "T002", ["TRN-077"]),
        notes="Same fix on another older transmission node (TRN-077, then on 3.2.1). 'Kolarissa keväällä' refers to T001."),
    "E006": dict(category="reinforcing", knowledge=dict(
        BOUNCE_COMMON, observed_on=["TRN-031"], scope=scope("transmission", OLDER),
        author=ERKKI, source_message_seqs=[1]),
        relations=[{"type": "reinforces", "target": "T001"}],
        expected_effects=merge("T001", "E006", ["TRN-031"]),
        notes="Finnish email. Mentions TRN-042 and TRN-077 as earlier cases; observed_on is the new device only."),
    "E002": dict(category="correct_fix", knowledge=dict(
        knowledge_type="troubleshooting_rule", summary=CABLE_SUMMARY, observed_on=["AGG-012"],
        scope=scope("aggregation_router"), events=["PATCH_CABLE_CHANGE"], symptoms=["CRC_ERRORS"],
        actions=["REPLACE_PATCH_CABLE"], avoid=["REPLACE_LINE_CARD"], outcome="worked", details=None,
        author=ANTTI, source_message_seqs=[1]),
        relations=[], expected_effects=[],
        notes="'old and new' -> no age limit, so AGG-003 (installed 2020) is in scope."),
    "T012": dict(category="reinforcing", knowledge=dict(
        knowledge_type="troubleshooting_rule", summary=CABLE_SUMMARY, observed_on=["AGG-003"],
        scope=scope("aggregation_router"), events=["MAINTENANCE", "PATCH_CABLE_CHANGE"], symptoms=["CRC_ERRORS"],
        actions=["REPLACE_PATCH_CABLE"], avoid=["REPLACE_LINE_CARD"], outcome="worked", details=None,
        author=ANTTI, source_message_seqs=[4, 5, 6], valid_from_seq=5),
        relations=[{"type": "reinforces", "target": "E002"}],
        expected_effects=merge("E002", "T012", ["AGG-003"]),
        notes="Mixed Finnish/English. 'Kajaani last autumn' refers to E002."),
    "T004": dict(category="correct_fix", knowledge=dict(
        COLD_COMMON, observed_on=["BTS-233"], scope=scope("base_station", OLDER),
        author=SANNA, source_message_seqs=[4, 5, 7, 8], valid_from_seq=7),
        relations=[], expected_effects=[], notes="BTS-233 on firmware 2.4.1."),
    "C001": dict(category="reinforcing", knowledge=dict(
        COLD_COMMON, observed_on=["BTS-210"], scope=scope("base_station", OLDER),
        author=SANNA, source_message_seqs=[4, 6, 7], valid_from_seq=6),
        relations=[{"type": "reinforces", "target": "T004"}],
        expected_effects=merge("T004", "C001", ["BTS-210"]),
        notes="Night-time phone call. BTS-210 then on 2.4.0. 'Kolarissa viime kesänä' refers to T004."),
    "T003": dict(category="correct_fix", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="When a microwave link flaps during heavy snow or icing, check the radome for ice before touching the radio; clearing the ice restores the link.",
        observed_on=["MW-405"], scope=scope("microwave_link"), events=["HEAVY_SNOW_ICE"], symptoms=["LINK_FLAPPING"],
        actions=["CLEAR_ICE_RADOME"], avoid=[], outcome="worked", details=None,
        author=ERKKI, source_message_seqs=[4, 6, 7, 8], valid_from_seq=7),
        relations=[], expected_effects=[], notes="Later disputed by T017."),
    "T005": dict(category="correct_fix", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="After the firmware 7.4 upgrade on an aggregation router the LACP bundle can stay down although member links are up; remove and re-add the port-channel member configuration.",
        observed_on=["AGG-007"], scope=scope("aggregation_router"), events=["FIRMWARE_UPGRADE"],
        symptoms=["LACP_BUNDLE_DOWN", "INTERFACE_UP"], actions=["READD_PORT_CHANNEL_MEMBER"], avoid=[],
        outcome="worked", details="Occurs after upgrading to firmware 7.4; no reboot needed.",
        author=ANTTI, source_message_seqs=[4, 6, 7], valid_from_seq=7),
        relations=[], expected_effects=[], notes="Upgrade event 2025-05-21 23:30."),
    "E003": dict(category="correct_fix", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="The firmware 1.4 upgrade on microwave links resets ATPC to off, so links fade in rain or snow; re-enable ATPC after every firmware upgrade.",
        observed_on=["MW-401", "MW-405", "MW-412"], scope=scope("microwave_link"), events=["FIRMWARE_UPGRADE"],
        symptoms=["LINK_FADING"], actions=["ENABLE_ATPC"], avoid=[], outcome="worked",
        details="Check ATPC after every firmware upgrade; not in the upgrade checklist.",
        author=JARI, source_message_seqs=[1]),
        relations=[], expected_effects=[], notes="Expert-to-expert email."),
    "T006": dict(category="correct_fix", knowledge=dict(
        knowledge_type="known_false_alarm",
        summary="A battery alarm on a base station after a very cold night is usually false, caused by the rectifier temperature sensor; check the sensor reading before dispatching.",
        observed_on=["BTS-250"], scope=scope("base_station"), events=["COLD_WEATHER"], symptoms=["BATTERY_ALARM"],
        actions=["CHECK_TEMP_SENSOR", "NO_DISPATCH_NEEDED"], avoid=[], outcome="worked",
        details="Sensor showed an impossible -40; battery voltage normal.",
        author=SANNA, source_message_seqs=[4, 5, 6], valid_from_seq=6),
        relations=[], expected_effects=[], notes="Saved a trip."),
    "T007": dict(category="correct_fix", knowledge=dict(
        knowledge_type="known_false_alarm",
        summary="On transmission nodes with 3.1.x firmware the fan alarm is a known sensor bug; if chassis temperature is normal, no dispatch is needed.",
        observed_on=["TRN-015"], scope=scope("transmission", firmware_below="3.2"), events=[], symptoms=["FAN_ALARM"],
        actions=["CHECK_CHASSIS_TEMP", "NO_DISPATCH_NEEDED"], avoid=[], outcome="worked", details=None,
        author=ERKKI, source_message_seqs=[2, 4], valid_from_seq=4),
        relations=[], expected_effects=[], notes="TRN-015 then on 3.1.2."),
    "E004": dict(category="correct_fix", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="On transmission nodes a hot-swapped line module shows as 'unknown module' until the inventory refresh (~3 minutes); wait before reseating or replacing it.",
        observed_on=["TRN-101"], scope=scope("transmission"), events=["MODULE_HOT_SWAP"], symptoms=["MODULE_UNKNOWN"],
        actions=["WAIT_INVENTORY_REFRESH"], avoid=["RESEAT_MODULE"], outcome="worked",
        details="Wait ~3 minutes; reseat once only if still unknown after 5 minutes.",
        author=ERKKI, source_message_seqs=[1]),
        relations=[], expected_effects=[], notes="Mixed Finnish/English email."),
    "T008": dict(category="correct_fix", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="When a microwave link loses alignment after a storm, check the mount bolts first and re-align; the radio does not need replacing.",
        observed_on=["MW-412"], scope=scope("microwave_link"), events=["STORM"], symptoms=["ALIGNMENT_LOST"],
        actions=["CHECK_MOUNT_BOLTS", "REALIGN_ANTENNA"], avoid=[], outcome="worked", details=None,
        author=JARI, source_message_seqs=[2, 4, 5], valid_from_seq=5),
        relations=[], expected_effects=[], notes=None),
    "T009": dict(category="correct_fix", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="Low optical levels on a transmission node after maintenance are usually a dirty connector; clean both ends with a click-cleaner instead of replacing the SFP.",
        observed_on=["TRN-112"], scope=scope("transmission"), events=["MAINTENANCE"], symptoms=["OPTICAL_LEVELS_LOW"],
        actions=["CLEAN_CONNECTOR"], avoid=["REPLACE_SFP"], outcome="worked", details=None,
        author=ERKKI, source_message_seqs=[4, 5, 6], valid_from_seq=5),
        relations=[], expected_effects=[], notes=None),
    "T010": dict(category="correct_fix", knowledge=dict(
        knowledge_type="known_false_alarm",
        summary="Nightly CPU spikes at 02:00 on aggregation routers are the config-backup job, not a fault; ignore unless above 95% for more than 10 minutes.",
        observed_on=["AGG-003"], scope=scope("aggregation_router"), events=[], symptoms=["HIGH_CPU"],
        actions=["NO_DISPATCH_NEEDED"], avoid=[], outcome="worked",
        details="Threshold: >95% for >10 min. Spike at 02:00 = config backup.",
        author=ANTTI, source_message_seqs=[4], valid_from_seq=4),
        relations=[], expected_effects=[], notes=None),
    "T011": dict(category="correct_fix", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="When a base station loses GPS sync after snowfall, check the GPS antenna heater fuse; replacing a blown fuse restores sync.",
        observed_on=["BTS-261"], scope=scope("base_station"), events=["HEAVY_SNOW_ICE"], symptoms=["GPS_SYNC_LOST"],
        actions=["REPLACE_FUSE"], avoid=[], outcome="worked", details=None,
        author=SANNA, source_message_seqs=[2, 3, 4, 5], valid_from_seq=5),
        relations=[], expected_effects=[], notes=None),
    "E005": dict(category="correct_fix", knowledge=dict(
        knowledge_type="hardware_compatibility",
        summary="Older transmission nodes reject the third-party SFPs from the latest spare batch (port says not supported and stays down); use only the approved part SFP-10G-LR-02.",
        observed_on=[], scope=scope("transmission", OLDER), events=["SFP_REPLACEMENT"],
        symptoms=["SFP_NOT_RECOGNISED", "INTERFACE_DOWN"], actions=["USE_APPROVED_PART"], avoid=[],
        outcome="worked", details="Approved part number SFP-10G-LR-02. Newer transmission nodes accept both.",
        author=ERKKI, source_message_seqs=[1]),
        relations=[], expected_effects=[], notes="No device id in the text; events show TRN-056 and TRN-023."),
    "T013": dict(category="correct_fix", knowledge=dict(
        knowledge_type="practical_tip",
        summary="The console port on older transmission nodes runs at 9600 baud, not 115200 as on the newer ones.",
        observed_on=[], scope=scope("transmission", OLDER), events=[], symptoms=[],
        actions=["SET_CONSOLE_BAUD_9600"], avoid=[], outcome="worked", details="Newer nodes: 115200.",
        author=ERKKI, source_message_seqs=[4, 5, 6], valid_from_seq=5),
        relations=[], expected_effects=[], notes="Vague device reference ('one of the old transmission boxes')."),
    # ---- 7.2 -------------------------------------------------------------
    "T014": dict(category="wrong_advice", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="Rebooting the whole older transmission node does not fix zero traffic after SFP replacement and causes a ~20 minute site outage.",
        observed_on=["TRN-015"], scope=scope("transmission", OLDER), events=["SFP_REPLACEMENT"],
        symptoms=["INTERFACE_UP", "ALARMS_CLEARED", "TRAFFIC_COUNTERS_ZERO"], actions=["REBOOT_UNIT"], avoid=[],
        outcome="failed", details="Reboot took ~20 min and dropped the whole site.",
        author=MIKKO, source_message_seqs=[2, 6, 7], valid_from_seq=6),
        relations=[], expected_effects=[], notes="Junior's wrong advice. Backs up T001's avoid list."),
    "T015": dict(category="wrong_advice", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="Replacing the SFP again does not fix zero traffic on an older transmission node when the port is up with normal optics.",
        observed_on=["TRN-031"], scope=scope("transmission", OLDER), events=["SFP_REPLACEMENT"],
        symptoms=["INTERFACE_UP", "OPTICAL_LEVELS_NORMAL", "TRAFFIC_COUNTERS_ZERO"], actions=["REPLACE_SFP"], avoid=[],
        outcome="failed", details=None,
        author=TIINA, source_message_seqs=[2, 4], valid_from_seq=4),
        relations=[], expected_effects=[], notes="Ends without a fix. Resolved months later in E006."),
    "T018": dict(category="wrong_advice", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="Removing and re-adding port-channel members does not bring up a down LACP bundle on older aggregation routers (firmware 7.2); that fix only applies after the 7.4 upgrade.",
        observed_on=["AGG-012"], scope=scope("aggregation_router", OLDER), events=[],
        symptoms=["LACP_BUNDLE_DOWN", "INTERFACE_UP"], actions=["READD_PORT_CHANNEL_MEMBER"], avoid=[],
        outcome="failed", details="AGG-012 on 7.2.0.",
        author=ANTTI, source_message_seqs=[2, 3, 6], valid_from_seq=3),
        relations=[], expected_effects=[], notes="v4 amendment 4: the wrong fix is the T005 fix."),
    "E007": dict(category="narrows_scope", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="Firmware 3.4 fixes the forwarding-state problem after SFP replacement on older transmission nodes; the interface disable/enable workaround is only needed below 3.4.",
        observed_on=["TRN-077", "TRN-015"], scope=scope("transmission", OLDER, firmware_at_least="3.4"),
        events=["SFP_REPLACEMENT", "FIRMWARE_UPGRADE"], symptoms=[], actions=[], avoid=[], outcome="worked",
        details="Fixed in firmware 3.4; TRN-042 and TRN-031 still below 3.4.",
        author=ERKKI, source_message_seqs=[1]),
        relations=[{"type": "narrows_scope", "target": "T001"}],
        expected_effects=[{"target": "T001", "set": {"scope.firmware_below": "3.4"}, "valid_to": None}],
        notes="Bounce fix stays valid for TRN-042, TRN-031, TRN-023, TRN-056; no longer for TRN-077, TRN-015."),
    "T016": dict(category="narrows_scope", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="Base station firmware 2.6 fixes the baseband not recovering after a power outage; the cold-restart workaround is only needed below 2.6.",
        observed_on=["BTS-210"], scope=scope("base_station", OLDER, firmware_at_least="2.6"),
        events=["POWER_OUTAGE", "FIRMWARE_UPGRADE"], symptoms=[], actions=[], avoid=[], outcome="worked",
        details="Fixed in firmware 2.6; BTS-233 still below 2.6.",
        author=SANNA, source_message_seqs=[1, 2, 4], valid_from_seq=2),
        relations=[{"type": "narrows_scope", "target": "T004"}],
        expected_effects=[{"target": "T004", "set": {"scope.firmware_below": "2.6"}, "valid_to": None}],
        notes="Cold restart stays valid for BTS-233, BTS-205, BTS-244."),
    "T017": dict(category="conflicting", knowledge=dict(
        knowledge_type="troubleshooting_rule",
        summary="Jari claims microwave link drops in hard frost are caused by the outdoor unit power supply, not ice, and that the PSU should be replaced; not confirmed.",
        observed_on=["MW-405"], scope=scope("microwave_link"), events=["COLD_WEATHER"], symptoms=["LINK_DOWN"],
        actions=["REPLACE_PSU"], avoid=[], outcome="unknown", details="-32 C, no ice on radome.",
        author=JARI, source_message_seqs=[2, 4], valid_from_seq=4),
        relations=[{"type": "conflicts_with", "target": "T003"}],
        expected_effects=[{"target": "T003", "set": {"status": "disputed"}}],
        notes="Evening (21:40). T017's own assertion is also disputed."),
    "T019": dict(category="noise", knowledge=None, relations=[], expected_effects=[],
                 notes="Christmas party planning; mentions AGG-007 jokingly."),
    "T020": dict(category="noise", knowledge=None, relations=[], expected_effects=[], notes="On-call shift swap."),
    "T021": dict(category="noise", knowledge=None, relations=[], expected_effects=[], notes="Status update only."),
    "C002": dict(category="noise", knowledge=None, relations=[], expected_effects=[],
                 notes="Speculation only, no fix, no conclusion."),
    # ---- 7.3 -------------------------------------------------------------
    "E008": dict(category="access_info", knowledge=dict(
        knowledge_type="access_info",
        summary="The private road to the TRN-042 / BTS-233 site near Kolari has a locked barrier; the key is in a lockbox at the neighbouring farm (red house before the barrier), code 2580.",
        observed_on=["TRN-042", "BTS-233"], scope=None, events=[], symptoms=[], actions=[], avoid=[],
        outcome="unknown", details="Lockbox code 2580; red house right before the barrier; return the key.",
        author=TIINA, source_message_seqs=[1]),
        relations=[], expected_effects=[], notes="Elisa's locked-barrier example written as an email."),
    "T022": dict(category="access_info", knowledge=dict(
        knowledge_type="access_info",
        summary="BTS-210 in Muonio: fence gate code 4471; the padlock sticks, lift the gate slightly to open it.",
        observed_on=["BTS-210"], scope=None, events=[], symptoms=[], actions=[], avoid=[],
        outcome="unknown", details="Gate code 4471. Padlock sticks: lift the gate slightly.",
        author=PEKKA, source_message_seqs=[2, 3], valid_from_seq=2),
        relations=[], expected_effects=[], notes="Superseded by T023."),
    "T023": dict(category="superseding", knowledge=dict(
        knowledge_type="access_info",
        summary="BTS-210 in Muonio: the gate code changed to 9035 (old code no longer works); the padlock still sticks, lift the gate slightly.",
        observed_on=["BTS-210"], scope=None, events=[], symptoms=[], actions=[], avoid=[],
        outcome="unknown", details="Gate code 9035 (replaces 4471). Padlock still sticks.",
        author=TIINA, source_message_seqs=[1, 3], valid_from_seq=1),
        relations=[{"type": "supersedes", "target": "T022"}],
        expected_effects=[{"target": "T022", "valid_to": "<T023.valid_from>"}],
        notes="v4 amendment 1: restates the padlock tip so superseding T022 loses nothing."),
}
