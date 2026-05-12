"""
Bahamas General Election Tracker - Results Scraper
Pulls live results from the Parliamentary Registration Department (PRD)
and any available aggregator pages, pushes to Firebase for the dashboard.

Run on Render every 3 min:  python scraper.py --loop
Run once locally to test:    python scraper.py
"""

import os
import re
import sys
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser

# ============================================================
# CONFIG
# ============================================================
FIREBASE_URL = os.environ.get(
    "FIREBASE_URL",
    "https://bahamas-tracker-default-rtdb.asia-southeast1.firebasedatabase.app"
).rstrip("/")
FIREBASE_SECRET = os.environ.get("FIREBASE_SECRET", "").strip()
FIREBASE_NODE = os.environ.get("FIREBASE_NODE", "bahamas_live").strip()
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "180"))

# Primary source: Nassau Guardian's BLOX-powered election results page.
# Updates automatically as PRD/news desks call constituencies.
PRIMARY_RESULTS_URL = os.environ.get(
    "PRIMARY_RESULTS_URL",
    "https://www.thenassauguardian.com/news/politics/election-results/"
).strip()

# Candidate slate — all 41 constituencies, sourced from Bahamas Gazette
# Notice of Nominations published April 17, 2026
CONSTITUENCIES = [
    # (id, name, plp, fnm, coi, [independents])
    ("bain_grants_town",       "Bain Town and Grants Town",             "Wayde Watson",        "Jay Philippe",          "Antonio Bain",        ["Brenda Pinder-Harris"]),
    ("bamboo_town",            "Bamboo Town",                            "Patricia Deveaux",    "Duane Sands",           "Maria Daxon",         []),
    ("bimini_berry",           "Bimini and Berry Islands",               "Randy Rolle",         "Carlton Bowleg",        "Hyram Rolle",         ["Paul Rolle"]),
    ("carmichael",             "Carmichael",                             "Keith Bell",          "Arinthia Komolafe",     "Charlotte Green",     ["O'Brien Thomas Knowles", "Simeon Mackey"]),
    ("cat_island",             "Cat Island, Rum Cay & San Salvador",     "Philip Davis",        "Mike Holmes",           "Donna McKay",         []),
    ("central_south_abaco",    "Central and South Abaco",                "Bradley Fox",         "Jeremy Sweeting",       "Crystal Williams",    []),
    ("central_south_eleuthera","Central and South Eleuthera",            "Clay Sweeting",       "Philippa Kelly",        "Bekera Grant-Taylor", []),
    ("central_grand_bahama",   "Central Grand Bahama",                   "Parkco R. Deal",      "Frazette Gibson",       "Iram Lewis",          []),
    ("centreville",            "Centreville",                            "Jomo Campbell",       "Darvin Russell",        "Jamaal Woodside",     []),
    ("east_grand_bahama",      "East Grand Bahama",                      "Monique Pratt",       "Kwasi Thompson",        "Dexter Edwards",      []),
    ("englerston",             "Englerston",                             "Glenys Hanna Martin", "Heather McDonald",      "Faith Percentie",     []),
    ("elizabeth",              "Elizabeth",                              "JoBeth Coleby-Davis", "Heather Watkins-Hunt",  "Donna Dorsett-Major", []),
    ("fort_charlotte",         "Fort Charlotte",                         "Sebastian Bastian",   "Travis Robinson",       "Daphaney Johnson",    []),
    ("fox_hill",               "Fox Hill",                               "Fred Mitchell",       "Nicholas Fox",          "Bobby Brown",         []),
    ("freetown",               "Freetown",                               "Wayne Munroe",        "Lincoln Deal II",       "Olivia Ingraham-Griffin", ["Andrew Johnson", "Patrice Hanna-Carey"]),
    ("garden_hills",           "Garden Hills",                           "Mario Bowleg",        "Rick Fox",              "Shantiqua Ayesha Cleare", []),
    ("golden_gates",           "Golden Gates",                           "Pia Glover-Rolle",    "Michael Foulkes",       "Sharmaine Adderley",  ["Anthony Rahming"]),
    ("golden_isles",           "Golden Isles",                           "Darron Pickstock",    "Brian Brown",           "Brian Rolle",         ["Karen Kim Butler"]),
    ("killarney",              "Killarney",                              "Robyn Lynes",         "Michela Barnett-Ellis", "Veronica McIver",     ["Hubert Minnis"]),
    ("long_island",            "Long Island",                            "Reneika Knowles",     "Andre Rollins",         "Shura Pratt",         ["Natasha Turnquest"]),
    ("mangrove_cay",           "Mangrove Cay and South Andros",          "Leon Lundy",          "Julian Gibson",         "Carlton Cleare",      []),
    ("marathon",               "Marathon",                               "Lisa Rahming",        "Jacqueline Penn-Knowles","Tyrone Greene",       []),
    ("marco_city",             "Marco City",                             "Eddie Whann",         "Michael Pintard",       "Jillian Bartlett",    []),
    ("mical",                  "MICAL",                                  "Ronnell Armbrister",  "James Leo Ferguson",    "Jermaine Higgs",      ["Kate Williamson"]),
    ("mount_moriah",           "Mount Moriah",                           "McKell Bonaby",       "Marvin Dames",          "Linda Stubbs",        []),
    ("nassau_village",         "Nassau Village",                         "Jamahl Strachan",     "Gadville McDonald",     "Stephen McQueen",     []),
    ("north_abaco",            "North Abaco",                            "Kirk Cornish",        "Terrece Bootle",        "Cay Mills",           ["Ryan Forbes"]),
    ("north_andros",           "North Andros",                           "Leonardo Lightbourne","Janice Oliver",         "Indera Laing",        []),
    ("north_eleuthera",        "North Eleuthera",                        "Sylvannus Petty",     "Howard Rickey Mackey",  "Natasha Mitchell",    []),
    ("pineridge",              "Pineridge",                              "Ginger Moxey",        "Charlene Reid",         "Daniel Mitchell",     ["Frederick McAlpine"]),
    ("pinewood",               "Pinewood",                               "Myles Laroda",        "Denarii Rolle",         "Lincoln Bain",        []),
    ("st_annes",               "Saint Anne's",                           "Keno Wong",           "Adrian White",          "Graham Weatherford",  ["Otis Forbes"]),
    ("st_barnabas",            "Saint Barnabas",                         "Michael Halkitis",    "Jamal Moss",            "Karen Butler",        []),
    ("sea_breeze",             "Sea Breeze",                             "Leslia Miller-Brice", "Trevania Clarke-Hall",  "William Knowles Jr.", []),
    ("south_beach",            "South Beach",                            "Bacchus Rolle",       "Darren Henfield",       "Karon Farrington",    []),
    ("southern_shores",        "Southern Shores",                        "S. Obie Roberts",     "Denalee Penn-Knowles",  "Kirk Farrington",     ["Leroy Major"]),
    ("st_james",               "St. James",                              "Owen Wells",          "Shanendon Cartwright",  "Latoya Bain",         ["Craig Powell", "Elkin Benedict Sutherland"]),
    ("tall_pines",             "Tall Pines",                             "Michael Darville",    "Serfent Rolle",         "Trevor Greene",       []),
    ("exumas_ragged",          "The Exumas and Ragged Island",           "Chester Cooper",      "Debra Moxey-Rolle",     "Byron Smith",         ["Deidre Ann Taylor"]),
    ("west_grand_bahama",      "West Grand Bahama",                      "Kingsley Smith",      "Omar Isaacs",           "Toni Stubbs-Albury",  []),
    ("yamacraw",               "Yamacraw",                               "Zane Lightbourne",    "Elsworth Johnson",      "Yvette Prince",       []),
]


# ============================================================
# HTTP helpers
# ============================================================
def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={
        "User-Agent": "BahamasTracker/1.0 SW2-Consulting",
        "Accept": "text/html,application/json,*/*",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_put_json(url, payload, timeout=20):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="PUT", headers={
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


# ============================================================
# Nassau Guardian results page parser
# Page structure: one <table> per race; first row is the race name
# (an <a> link in the header), subsequent rows are candidates with
# "Name (PARTY)" + percentage + votes, footer row has "(X%) precincts reporting Updated ..."
# ============================================================
class NassauGuardianParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.races = []  # list of dicts: {name, candidates: [{name, party, votes, pct, incumbent}], reporting}
        self._cur_race = None
        self._cur_row_cells = None
        self._cur_cell_text = None
        self._cur_cell_links = None  # list of link text seen in this cell
        self._in_link = False
        self._link_buf = None
        self._in_table = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._in_table = True
            self._cur_race = {"name": None, "candidates": [], "reporting": None, "updated": None}
        elif tag == "tr" and self._in_table:
            self._cur_row_cells = []
        elif tag in ("td", "th") and self._cur_row_cells is not None:
            self._cur_cell_text = []
            self._cur_cell_links = []
        elif tag == "a" and self._cur_cell_text is not None:
            self._in_link = True
            self._link_buf = []

    def handle_data(self, data):
        if self._in_link and self._link_buf is not None:
            self._link_buf.append(data)
        if self._cur_cell_text is not None:
            self._cur_cell_text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._in_link:
            link_text = " ".join("".join(self._link_buf).split()).strip()
            if link_text and self._cur_cell_links is not None:
                self._cur_cell_links.append(link_text)
            self._in_link = False
            self._link_buf = None
        elif tag in ("td", "th") and self._cur_cell_text is not None:
            text = " ".join("".join(self._cur_cell_text).split()).strip()
            self._cur_row_cells.append({"text": text, "links": list(self._cur_cell_links or [])})
            self._cur_cell_text = None
            self._cur_cell_links = None
        elif tag == "tr" and self._cur_row_cells is not None:
            self._process_row(self._cur_row_cells)
            self._cur_row_cells = None
        elif tag == "table" and self._in_table:
            if self._cur_race and self._cur_race["name"] and self._cur_race["candidates"]:
                self.races.append(self._cur_race)
            self._cur_race = None
            self._in_table = False

    def _process_row(self, cells):
        if not cells or self._cur_race is None:
            return
        # Race header row: a single cell with a link, no numbers
        if len(cells) == 1 and cells[0]["links"]:
            link = cells[0]["links"][0]
            # Skip "Path to Majority Seats" — that's a summary row, not a constituency
            if "path to majority" in link.lower():
                self._cur_race["name"] = "__SUMMARY__"
            else:
                self._cur_race["name"] = link
            return
        # Candidate row: name(PARTY) | pct | (bar/spacer) | votes
        if len(cells) >= 3:
            first_text = cells[0]["text"]
            # Detect party tag
            party_match = re.search(r"\(([A-Z]{2,4})\)", first_text)
            if party_match:
                party = party_match.group(1)
                # Name is everything before the party paren
                name = first_text[:party_match.start()].strip()
                # Strip incumbent asterisk and trailing punct
                incumbent = name.endswith("*") or first_text.endswith("*") or any("*" in c["text"] and "incumbent" in c["text"].lower() for c in cells)
                name = name.rstrip(" *").strip()
                # Pct is usually 2nd cell, votes is last cell
                pct_text = cells[1]["text"]
                votes_text = cells[-1]["text"]
                pct = None
                m = re.search(r"([\d.]+)\s*%", pct_text)
                if m:
                    try: pct = float(m.group(1))
                    except: pass
                votes = 0
                m = re.search(r"\b([\d,]+)\b", votes_text)
                if m:
                    try: votes = int(m.group(1).replace(",", ""))
                    except: votes = 0
                self._cur_race["candidates"].append({
                    "name": name, "party": party, "votes": votes, "pct": pct, "incumbent": incumbent,
                })
                return
        # Footer row: "(X%) precincts reporting Updated Y hrs ago"
        joined = " ".join(c["text"] for c in cells).lower()
        if "precincts reporting" in joined or "% reporting" in joined:
            m = re.search(r"\(?\s*([\d.]+)\s*%\s*\)?\s*precincts reporting", joined)
            if m:
                try: self._cur_race["reporting"] = float(m.group(1))
                except: pass
            m = re.search(r"updated\s+(.+)", joined)
            if m:
                self._cur_race["updated"] = m.group(1).strip()


# ============================================================
# Constituency name matcher — Nassau Guardian uses slightly different
# spellings than the official slate (e.g. "Bains Town" vs "Bain Town",
# "Bimini and The Berry Islands" vs "Bimini and Berry Islands")
# ============================================================
def _norm_words(s):
    if not s: return ""
    s = s.lower()
    s = re.sub(r"['\"\u2018\u2019\u201c\u201d.,]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_match(target, found):
    """Match a person by last name + first initial."""
    t = _norm_words(target).split()
    c = _norm_words(found).split()
    if not t or not c: return False
    if t[-1] != c[-1]: return False
    return t[0][:1] == c[0][:1]


def constituency_norm(s):
    if not s: return ""
    s = s.lower()
    # Drop common filler words
    s = re.sub(r"\b(the|and|of|&)\b", " ", s)
    s = re.sub(r"['\"\u2018\u2019\u201c\u201d.,]", "", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Stem: drop trailing 's' on words 3+ chars (handles "Bains" → "Bain", "Pines" → "Pine", "Shores" → "Shore")
    words = []
    for w in s.split():
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            words.append(w[:-1])
        else:
            words.append(w)
    return " ".join(words)


def match_constituency(target_name, found_name):
    a = constituency_norm(target_name)
    b = constituency_norm(found_name)
    if a == b: return True
    # Token-overlap: both directions need ≥60% overlap (handles "Bimini and The Berry Islands" vs "Bimini and Berry Islands")
    at = set(a.split())
    bt = set(b.split())
    if not at or not bt: return False
    overlap_a = len(at & bt) / len(at)
    overlap_b = len(at & bt) / len(bt)
    return overlap_a >= 0.6 and overlap_b >= 0.6


def build_results_from_races(scraped_races):
    """
    Match scraped races (by constituency name) to our slate (by constituency id).
    Within each match, assign votes by party tag (PLP/FNM/COI/IND).
    Independents are keyed by candidate name match.
    """
    results = {}
    matched_constituencies = set()

    for cid, cname, plp, fnm, coi, indeps in CONSTITUENCIES:
        slot = {
            "plp_votes": None, "fnm_votes": None, "coi_votes": None,
            "indep_votes": {n: None for n in indeps},
            "total_votes": None, "reporting": None, "matched": False,
        }

        # Find the corresponding scraped race
        scraped = None
        for sr in scraped_races:
            if sr.get("name") == "__SUMMARY__": continue
            if match_constituency(cname, sr["name"] or ""):
                scraped = sr
                break

        if scraped:
            matched_constituencies.add(cid)
            slot["matched"] = True
            slot["reporting"] = scraped.get("reporting")
            for c in scraped["candidates"]:
                party = c["party"]
                votes = c["votes"]
                if party == "PLP":
                    slot["plp_votes"] = votes
                elif party == "FNM":
                    slot["fnm_votes"] = votes
                elif party == "COI":
                    slot["coi_votes"] = votes
                elif party == "IND":
                    # Match by last name + first initial
                    matched_indep = None
                    for known in indeps:
                        if name_match(known, c["name"]):
                            matched_indep = known
                            break
                    if matched_indep:
                        slot["indep_votes"][matched_indep] = votes
                    else:
                        # Unknown independent — add to dict anyway under their actual name
                        slot["indep_votes"][c["name"]] = votes
            # Total
            total = 0
            for v in (slot["plp_votes"], slot["fnm_votes"], slot["coi_votes"]):
                if v: total += v
            for v in slot["indep_votes"].values():
                if v: total += v
            slot["total_votes"] = total if total > 0 else None

        results[cid] = slot

    return results, matched_constituencies


# ============================================================
# Build payload
# ============================================================
def build_payload(parsed_results, source_url):
    races = {}
    plp_seats = 0
    fnm_seats = 0
    coi_seats = 0
    indep_seats = 0
    reporting_count = 0

    for cid, cname, plp, fnm, coi, indeps in CONSTITUENCIES:
        r = parsed_results.get(cid, {}) if parsed_results else {}
        plp_v = r.get("plp_votes") or 0
        fnm_v = r.get("fnm_votes") or 0
        coi_v = r.get("coi_votes") or 0
        indep_dict = r.get("indep_votes") or {n: 0 for n in indeps}
        total = r.get("total_votes") or 0

        # Determine leader
        candidates = [
            ("PLP", plp, plp_v),
            ("FNM", fnm, fnm_v),
            ("COI", coi, coi_v),
        ] + [("IND", n, indep_dict.get(n) or 0) for n in indeps]

        candidates.sort(key=lambda x: x[2], reverse=True)
        leader_party = candidates[0][0] if candidates and candidates[0][2] > 0 else None

        if leader_party == "PLP": plp_seats += 1
        elif leader_party == "FNM": fnm_seats += 1
        elif leader_party == "COI": coi_seats += 1
        elif leader_party == "IND": indep_seats += 1

        if r.get("matched"):
            reporting_count += 1

        races[cid] = {
            "name": cname,
            "plp_name": plp,
            "fnm_name": fnm,
            "coi_name": coi,
            "indep_names": indeps,
            "plp_votes": plp_v if plp_v else None,
            "fnm_votes": fnm_v if fnm_v else None,
            "coi_votes": coi_v if coi_v else None,
            "indep_votes": indep_dict,
            "total_votes": total if total else None,
            "leader_party": leader_party,
            "reporting": r.get("reporting"),
        }

    return {
        "races": races,
        "totals": {
            "PLP": plp_seats,
            "FNM": fnm_seats,
            "COI": coi_seats,
            "IND": indep_seats,
            "constituencies_reporting": reporting_count,
            "constituencies_total": len(CONSTITUENCIES),
        },
        "meta": {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "source": source_url or "Awaiting PRD results page",
            "polls_close": "2026-05-12T22:00:00Z",  # 6 PM AST = 22:00 UTC
        },
    }


# ============================================================
# Firebase push
# ============================================================
def push_to_firebase(payload):
    if not FIREBASE_URL or "YOUR-PROJECT" in FIREBASE_URL:
        print("[firebase] FIREBASE_URL not set, printing payload:")
        print(json.dumps(payload, indent=2)[:1500])
        return False
    url = f"{FIREBASE_URL}/{FIREBASE_NODE}.json"
    if FIREBASE_SECRET:
        url += f"?auth={urllib.parse.quote(FIREBASE_SECRET)}"
    try:
        http_put_json(url, payload)
        leaders = payload["totals"]
        print(f"[firebase] pushed OK · PLP {leaders['PLP']} FNM {leaders['FNM']} COI {leaders['COI']} IND {leaders['IND']} (reporting {leaders['constituencies_reporting']}/{leaders['constituencies_total']})")
        return True
    except Exception as exc:
        print(f"[firebase] push failed: {exc}", file=sys.stderr)
        return False


# ============================================================
# Main
# ============================================================
def run_once():
    print(f"\n=== run @ {datetime.now().isoformat(timespec='seconds')} ===")

    parsed = {}
    source_url = PRIMARY_RESULTS_URL

    try:
        print(f"[fetch] {source_url}")
        html = http_get(source_url)
        p = NassauGuardianParser()
        p.feed(html)
        scraped = [r for r in p.races if r.get("name") and r["name"] != "__SUMMARY__"]
        print(f"[parse] found {len(scraped)} constituency tables")

        parsed, matched = build_results_from_races(scraped)
        with_votes = sum(1 for v in parsed.values() if v.get("total_votes"))
        print(f"[match] {len(matched)}/{len(CONSTITUENCIES)} constituencies matched, {with_votes} with votes")

        # Diagnose unmatched
        if len(matched) < len(CONSTITUENCIES):
            missing = [cname for cid, cname, *_ in CONSTITUENCIES if cid not in matched]
            scraped_names = [r["name"] for r in scraped]
            print(f"[match] missing: {missing[:3]}{'...' if len(missing) > 3 else ''}")
            print(f"[match] scraped names sample: {scraped_names[:5]}")
    except Exception as exc:
        print(f"[fetch] failed: {exc}", file=sys.stderr)

    payload = build_payload(parsed, source_url)
    push_to_firebase(payload)


def run_loop():
    while True:
        try:
            run_once()
        except Exception as exc:
            print(f"[loop] error: {exc}", file=sys.stderr)
        print(f"[loop] sleep {POLL_SECONDS}s")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--loop":
        run_loop()
    else:
        run_once()
