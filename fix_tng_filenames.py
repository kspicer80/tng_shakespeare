#!/usr/bin/env python3
"""
fix_tng_filenames.py
--------------------
Renames the already-downloaded TNG episode files to correct S/E numbers.

The original scraper misread chakoteya's sequential episode codes (101, 102…)
as season/episode pairs, so everything above ep 99 got mislabeled.

This script uses the canonical TNG season/episode map to rename files in-place.
No re-downloading needed.

Usage:
    python fix_tng_filenames.py [--dry-run]
"""

import os
import re
import sys
import shutil
from pathlib import Path

ROOT    = Path(__file__).parent
TNG_RAW = ROOT / "tng" / "raw"
DRY_RUN = "--dry-run" in sys.argv

# ---------------------------------------------------------------------------
# Canonical TNG episode list
# (sequential_number, season, episode, title)
# Source: Memory Alpha / Wikipedia
# ---------------------------------------------------------------------------

TNG_EPISODES = [
    # Season 1 (26 episodes)
    (1,   1,  1,  "Encounter_at_Farpoint"),
    (2,   1,  2,  "The_Naked_Now"),
    (3,   1,  3,  "Code_of_Honour"),
    (4,   1,  4,  "The_Last_Outpost"),
    (5,   1,  5,  "Where_No_One_Has_Gone_Before"),
    (6,   1,  6,  "Lonely_Among_Us"),
    (7,   1,  7,  "Justice"),
    (8,   1,  8,  "The_Battle"),
    (9,   1,  9,  "Hide_Q"),
    (10,  1, 10,  "Haven"),
    (11,  1, 11,  "The_Big_Goodbye"),
    (12,  1, 12,  "Datalore"),
    (13,  1, 13,  "Angel_One"),
    (14,  1, 14,  "11001001"),
    (15,  1, 15,  "Too_Short_A_Season"),
    (16,  1, 16,  "When_The_Bough_Breaks"),
    (17,  1, 17,  "Home_Soil"),
    (18,  1, 18,  "Coming_of_Age"),
    (19,  1, 19,  "Heart_Of_Glory"),
    (20,  1, 20,  "The_Arsenal_Of_Freedom"),
    (21,  1, 21,  "Symbiosis"),
    (22,  1, 22,  "Skin_Of_Evil"),
    (23,  1, 23,  "Well_Always_Have_Paris"),
    (24,  1, 24,  "Conspiracy"),
    (25,  1, 25,  "The_Neutral_Zone"),
    # Season 2 (22 episodes)
    (26,  2,  1,  "The_Child"),
    (27,  2,  2,  "Where_Silence_Has_Lease"),
    (28,  2,  3,  "Elementary_Dear_Data"),
    (29,  2,  4,  "The_Outrageous_Okona"),
    (30,  2,  5,  "Loud_as_a_Whisper"),
    (31,  2,  6,  "The_Schizoid_Man"),
    (32,  2,  7,  "Unnatural_Selection"),
    (33,  2,  8,  "A_Matter_of_Honour"),
    (34,  2,  9,  "The_Measure_of_a_Man"),
    (35,  2, 10,  "The_Dauphin"),
    (36,  2, 11,  "Contagion"),
    (37,  2, 12,  "The_Royale"),
    (38,  2, 13,  "Time_Squared"),
    (39,  2, 14,  "The_Icarus_Factor"),
    (40,  2, 15,  "Pen_Pals"),
    (41,  2, 16,  "Q_Who"),
    (42,  2, 17,  "Samaritan_Snare"),
    (43,  2, 18,  "Up_The_Long_Ladder"),
    (44,  2, 19,  "Manhunt"),
    (45,  2, 20,  "The_Emissary"),
    (46,  2, 21,  "Peak_Performance"),
    (47,  2, 22,  "Shades_Of_Gray"),
    # Season 3 (26 episodes)
    (48,  3,  1,  "Evolution"),
    (49,  3,  2,  "The_Ensigns_of_Command"),
    (50,  3,  3,  "The_Survivors"),
    (51,  3,  4,  "Who_Watches_The_Watchers"),
    (52,  3,  5,  "The_Bonding"),
    (53,  3,  6,  "Booby_Trap"),
    (54,  3,  7,  "The_Enemy"),
    (55,  3,  8,  "The_Price"),
    (56,  3,  9,  "The_Vengeance_Factor"),
    (57,  3, 10,  "The_Defector"),
    (58,  3, 11,  "The_Hunted"),
    (59,  3, 12,  "The_High_Ground"),
    (60,  3, 13,  "Deja_Q"),
    (61,  3, 14,  "A_Matter_Of_Perspective"),
    (62,  3, 15,  "Yesterdays_Enterprise"),
    (63,  3, 16,  "The_Offspring"),
    (64,  3, 17,  "Sins_Of_The_Father"),
    (65,  3, 18,  "Allegiance"),
    (66,  3, 19,  "Captains_Holiday"),
    (67,  3, 20,  "Tin_Man"),
    (68,  3, 21,  "Hollow_Pursuits"),
    (69,  3, 22,  "The_Most_Toys"),
    (70,  3, 23,  "Sarek"),
    (71,  3, 24,  "Menage_a_Troi"),
    (72,  3, 25,  "Transfigurations"),
    (73,  3, 26,  "Best_Of_Both_Worlds_part_1"),
    # Season 4 (26 episodes)
    (74,  4,  1,  "Best_of_Both_Worlds_part_2"),
    (75,  4,  2,  "Family"),
    (76,  4,  3,  "Brothers"),
    (77,  4,  4,  "Suddenly_Human"),
    (78,  4,  5,  "Remember_Me"),
    (79,  4,  6,  "Legacy"),
    (80,  4,  7,  "Reunion"),
    (81,  4,  8,  "Future_Imperfect"),
    (82,  4,  9,  "Final_Mission"),
    (83,  4, 10,  "The_Loss"),
    (84,  4, 11,  "Datas_Day"),
    (85,  4, 12,  "The_Wounded"),
    (86,  4, 13,  "Devils_Due"),
    (87,  4, 14,  "Clues"),
    (88,  4, 15,  "First_Contact"),
    (89,  4, 16,  "Galaxys_Child"),
    (90,  4, 17,  "Night_Terrors"),
    (91,  4, 18,  "Identity_Crisis"),
    (92,  4, 19,  "The_Nth_Degree"),
    (93,  4, 20,  "Qpid"),
    (94,  4, 21,  "The_Drumhead"),
    (95,  4, 22,  "Half_a_Life"),
    (96,  4, 23,  "The_Host"),
    (97,  4, 24,  "The_Minds_Eye"),
    (98,  4, 25,  "In_Theory"),
    (99,  4, 26,  "Redemption"),
    # Season 5 (26 episodes)
    (100, 5,  1,  "Redemption_part_2"),
    (101, 5,  2,  "Darmok"),
    (102, 5,  3,  "Ensign_Ro"),
    (103, 5,  4,  "Silicon_Avatar"),
    (104, 5,  5,  "Disaster"),
    (105, 5,  6,  "The_Game"),
    (106, 5,  7,  "Unification_part_1"),
    (107, 5,  8,  "Unification_part_2"),
    (108, 5,  9,  "A_Matter_Of_Time"),
    (109, 5, 10,  "New_Ground"),
    (110, 5, 11,  "Hero_Worship"),
    (111, 5, 12,  "Violations"),
    (112, 5, 13,  "The_Masterpiece_Society"),
    (113, 5, 14,  "Conundrum"),
    (114, 5, 15,  "Power_Play"),
    (115, 5, 16,  "Ethics"),
    (116, 5, 17,  "The_Outcast"),
    (117, 5, 18,  "Cause_and_Effect"),
    (118, 5, 19,  "The_First_Duty"),
    (119, 5, 20,  "Cost_of_Living"),
    (120, 5, 21,  "The_Perfect_Mate"),
    (121, 5, 22,  "Imaginary_Friend"),
    (122, 5, 23,  "I_Borg"),
    (123, 5, 24,  "The_Next_Phase"),
    (124, 5, 25,  "The_Inner_Light"),
    (125, 5, 26,  "Times_Arrow_part_1"),
    # Season 6 (26 episodes)
    (126, 6,  1,  "Times_Arrow_part_2"),
    (127, 6,  2,  "Realm_of_Fear"),
    (128, 6,  3,  "Man_of_the_People"),
    (129, 6,  4,  "Relics"),
    (130, 6,  5,  "Schisms"),
    (131, 6,  6,  "True_Q"),
    (132, 6,  7,  "Rascals"),
    (133, 6,  8,  "A_Fistful_of_Datas"),
    (134, 6,  9,  "The_Quality_of_Life"),
    (135, 6, 10,  "Chain_of_Command_part_1"),
    (136, 6, 11,  "Chain_of_Command_part_2"),
    (137, 6, 12,  "Ship_in_a_Bottle"),
    (138, 6, 13,  "Aquiel"),
    (139, 6, 14,  "Face_of_the_Enemy"),
    (140, 6, 15,  "Tapestry"),
    (141, 6, 16,  "Birthright_part_1"),
    (142, 6, 17,  "Birthright_part_2"),
    (143, 6, 18,  "Starship_Mine"),
    (144, 6, 19,  "Lessons"),
    (145, 6, 20,  "The_Chase"),
    (146, 6, 21,  "Frame_of_Mind"),
    (147, 6, 22,  "Suspicions"),
    (148, 6, 23,  "Rightful_Heir"),
    (149, 6, 24,  "Second_Chances"),
    (150, 6, 25,  "Timescape"),
    (151, 6, 26,  "Descent_part_1"),
    # Season 7 (25 episodes + feature-length finale = 26 files)
    (152, 7,  1,  "Descent_part_2"),
    (153, 7,  2,  "Liaisons"),
    (154, 7,  3,  "Interface"),
    (155, 7,  4,  "Gambit_part_1"),
    (156, 7,  5,  "Gambit_part_2"),
    (157, 7,  6,  "Phantasms"),
    (158, 7,  7,  "Dark_Page"),
    (159, 7,  8,  "Attached"),
    (160, 7,  9,  "Force_of_Nature"),
    (161, 7, 10,  "Inheritance"),
    (162, 7, 11,  "Parallels"),
    (163, 7, 12,  "The_Pegasus"),
    (164, 7, 13,  "Homeward"),
    (165, 7, 14,  "Sub_Rosa"),
    (166, 7, 15,  "Lower_Decks"),
    (167, 7, 16,  "Thine_Own_Self"),
    (168, 7, 17,  "Masks"),
    (169, 7, 18,  "Eye_of_the_Beholder"),
    (170, 7, 19,  "Genesis"),
    (171, 7, 20,  "Journeys_End"),
    (172, 7, 21,  "Firstborn"),
    (173, 7, 22,  "Bloodlines"),
    (174, 7, 23,  "Emergence"),
    (175, 7, 24,  "Preemptive_Strike"),
    (176, 7, 25,  "All_Good_Things"),
]

# ---------------------------------------------------------------------------
# Build a lookup: current (wrong) filename slug → correct new filename
# The scraper named files by sequential code, so ep 101 → S01E01_...
# We match on the title slug since that's stable.
# ---------------------------------------------------------------------------

def slugify(s: str) -> str:
    """Lowercase, strip punctuation, collapse spaces — for fuzzy matching."""
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", "_", s.strip())
    return s


def main():
    existing = sorted(TNG_RAW.glob("*.txt"))
    if not existing:
        print(f"No files found in {TNG_RAW}")
        return

    # Map existing files by their title slug
    existing_by_slug = {}
    for path in existing:
        # Strip the SxxExx_ prefix to get the title portion
        stem = path.stem
        title_part = re.sub(r"^S\d{2}E\d{2}_", "", stem)
        existing_by_slug[slugify(title_part)] = path

    renamed = 0
    not_matched = []

    for seq, season, episode, title in TNG_EPISODES:
        target_slug = slugify(title)
        old_path = existing_by_slug.get(target_slug)

        if old_path is None:
            # Try partial match
            for slug, path in existing_by_slug.items():
                if target_slug in slug or slug in target_slug:
                    old_path = path
                    break

        new_name = f"S{season:02d}E{episode:02d}_{title}.txt"
        new_path = TNG_RAW / new_name

        if old_path is None:
            not_matched.append((seq, season, episode, title))
            continue

        if old_path.name == new_name:
            print(f"  OK (already correct): {new_name}")
            continue

        if DRY_RUN:
            print(f"  WOULD RENAME: {old_path.name}")
            print(f"             → {new_name}")
        else:
            old_path.rename(new_path)
            print(f"  RENAMED: {old_path.name}")
            print(f"        → {new_name}")
        renamed += 1

    print(f"\n{'DRY RUN: ' if DRY_RUN else ''}Renamed {renamed} files.")

    if not_matched:
        print(f"\nCould not match {len(not_matched)} episodes:")
        for seq, s, e, t in not_matched:
            print(f"  seq={seq:3d}  S{s:02d}E{e:02d}  {t}")
        print("\nThese may need manual matching or a re-scrape.")


if __name__ == "__main__":
    if DRY_RUN:
        print("=== DRY RUN MODE — no files will be changed ===\n")
    main()
