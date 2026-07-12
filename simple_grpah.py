"""Generate social-media-ready graphs from live dashboard data.

Run locally (on Windows) at the end of Halloween night. Reads credentials from
local_application/config.json and queries the live API — no local DB access needed.

Outputs two PNGs in the project root:
  trickortreat_by_year.png  — all-time year-over-year bar chart
  trickortreat_tonight.png  — 15-minute interval timeline for the current evening

Run: python simple_grpah.py
"""
import json
import os
import requests
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from datetime import datetime, timezone, timedelta
from collections import defaultdict

CONFIG_PATH = os.path.join('local_application', 'config.json')

with open(CONFIG_PATH) as f:
    config = json.load(f)

API_URL = config['api_url'].rstrip('/')
HEADERS = {'X-API-Key': config['api_key']}

DARK_BG = '#1a1a2e'
CARD_BG = '#16213e'
ORANGE = '#ff7b00'
ORANGE_LIGHT = '#ffa040'
TEXT = '#e0e0e0'
GRID = '#2a2a4a'


def fetch(endpoint):
    r = requests.get(f"{API_URL}{endpoint}", headers=HEADERS, timeout=10)
    r.raise_for_status()
    return r.json()


def apply_dark_style(fig, ax):
    fig.patch.set_facecolor(DARK_BG)
    ax.set_facecolor(CARD_BG)
    ax.tick_params(colors=TEXT, labelsize=11)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    ax.title.set_color(TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.grid(axis='y', color=GRID, alpha=0.6, linewidth=0.8)
    ax.set_axisbelow(True)


# --- Graph A: Year-over-year totals ---

def graph_year_totals():
    historical = fetch('/historical_data')  # {year: {time_slot: {total, average, count}}}
    current_entries = fetch('/current_data')

    year_totals = defaultdict(int)
    for year, slots in historical.items():
        for slot in slots.values():
            year_totals[int(year)] += slot['total']

    # Add current year from raw events if it hasn't been archived yet
    current_year = datetime.now().year
    if str(current_year) not in historical:
        for entry in current_entries:
            if not entry.get('test'):
                year_totals[current_year] += entry.get('count', 1)

    years = sorted(year_totals.keys())
    counts = [year_totals[y] for y in years]

    fig, ax = plt.subplots(figsize=(12, 6.75))
    apply_dark_style(fig, ax)

    bars = ax.bar(years, counts, color=ORANGE, edgecolor=DARK_BG, linewidth=1.5, width=0.6)

    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(counts) * 0.015,
            str(count),
            ha='center', va='bottom',
            fontsize=13, fontweight='bold', color=TEXT
        )

    ax.set_xlabel('Year', fontsize=13, labelpad=8)
    ax.set_ylabel('Total Trick-or-Treaters', fontsize=13, labelpad=8)
    ax.set_title('Trick-or-Treaters by Year', fontsize=17, fontweight='bold', pad=16)
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years], fontsize=12)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.set_ylim(0, max(counts) * 1.15)

    plt.tight_layout()
    out = 'trickortreat_by_year.png'
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=DARK_BG)
    plt.close()
    print(f"Saved {out}")
    for y, c in zip(years, counts):
        print(f"  {y}: {c}")


# --- Graph B: Tonight's timeline ---

def graph_tonight():
    entries = fetch('/current_data')
    real = [e for e in entries if not e.get('test')]

    if not real:
        print("No current-year data to plot for tonight's timeline.")
        return

    # EDT on Halloween (Oct 31) is UTC-4; DST ends first Sunday in November
    EASTERN = timezone(timedelta(hours=-4))

    buckets = defaultdict(int)
    for e in real:
        ts = datetime.fromisoformat(e['timestamp'].replace('Z', '+00:00'))
        ts_local = ts.astimezone(EASTERN)
        slot = ts_local.replace(minute=(ts_local.minute // 15) * 15, second=0, microsecond=0)
        buckets[slot] += e.get('count', 1)

    if not buckets:
        print("Could not parse timestamps for tonight's timeline.")
        return

    slots = sorted(buckets.keys())
    counts = [buckets[s] for s in slots]

    peak_idx = counts.index(max(counts))
    peak_slot = slots[peak_idx]
    peak_count = counts[peak_idx]

    fig, ax = plt.subplots(figsize=(12, 6.75))
    apply_dark_style(fig, ax)

    bars = ax.bar(range(len(slots)), counts, color=ORANGE, edgecolor=DARK_BG, linewidth=1, width=0.7)
    bars[peak_idx].set_color(ORANGE_LIGHT)

    offset_dir = 1 if peak_idx < len(slots) - 3 else -3
    ax.annotate(
        f"Peak: {peak_slot.strftime('%I:%M %p').lstrip('0')}\n{peak_count} visitors",
        xy=(peak_idx, peak_count),
        xytext=(peak_idx + offset_dir, peak_count * 0.82),
        color=TEXT, fontsize=11, fontweight='bold',
        arrowprops=dict(arrowstyle='->', color=TEXT, lw=1.5),
    )

    total = sum(counts)
    year = slots[0].year if slots else datetime.now().year
    ax.set_title(
        f"{year} Halloween Night  •  {total} Total Trick-or-Treaters",
        fontsize=16, fontweight='bold', pad=16
    )
    ax.set_xlabel('Time of Evening (Eastern)', fontsize=13, labelpad=8)
    ax.set_ylabel('Visitors per 15 min', fontsize=13, labelpad=8)

    step = max(1, len(slots) // 10)
    ax.set_xticks(range(0, len(slots), step))
    ax.set_xticklabels(
        [slots[i].strftime('%I:%M %p').lstrip('0') for i in range(0, len(slots), step)],
        fontsize=10, rotation=30, ha='right'
    )
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.set_ylim(0, max(counts) * 1.2)

    plt.tight_layout()
    out = 'trickortreat_tonight.png'
    plt.savefig(out, dpi=150, bbox_inches='tight', facecolor=DARK_BG)
    plt.close()
    print(f"Saved {out}")


if __name__ == '__main__':
    graph_year_totals()
    graph_tonight()
