"""Export dual-signal detector flow diagram to PNG and PDF."""

from matplotlib import pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.backends.backend_pdf import PdfPages

OUTPUT_BASE = "/home/sandbox/personal-repos/Challenge_SystemHealthAlarm/Welford/dual_signal_detector_flow"
DPI = 200
FIGSIZE = (14, 18)

BOX_STYLE = dict(boxstyle="round,pad=0.45", linewidth=1.6)
DIAMOND_STYLE = dict(boxstyle="round,pad=0.35", linewidth=1.6)
COLORS = {
    "start": "#E8F4FD",
    "process": "#FFFFFF",
    "decision": "#FFF4E5",
    "alert": "#FDE8E8",
    "ok": "#E8F8EE",
    "edge": "#2F3B4A",
    "text": "#1F2933",
    "arrow": "#4B5563",
}


def add_box(ax, xy, text, width, height, facecolor, fontsize=10, weight="normal"):
    x, y = xy
    patch = FancyBboxPatch(
        (x - width / 2, y - height / 2),
        width,
        height,
        facecolor=facecolor,
        edgecolor=COLORS["edge"],
        **BOX_STYLE,
    )
    ax.add_patch(patch)
    ax.text(
        x,
        y,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=COLORS["text"],
        weight=weight,
        wrap=True,
    )
    return (x, y, width, height)


def add_diamond(ax, xy, text, width, height):
    x, y = xy
    patch = FancyBboxPatch(
        (x - width / 2, y - height / 2),
        width,
        height,
        facecolor=COLORS["decision"],
        edgecolor=COLORS["edge"],
        **DIAMOND_STYLE,
    )
    ax.add_patch(patch)
    ax.text(x, y, text, ha="center", va="center", fontsize=10, color=COLORS["text"], wrap=True)
    return (x, y, width, height)


def arrow(ax, start, end, text=None, text_offset=(0, 0)):
    sx, sy, _, sh = start
    ex, ey, _, eh = end
    y_start = sy - sh / 2
    y_end = ey + eh / 2
    if abs(sx - ex) < 0.2:
        path = FancyArrowPatch(
            (sx, y_start),
            (ex, y_end),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.4,
            color=COLORS["arrow"],
            shrinkA=2,
            shrinkB=2,
        )
    else:
        path = FancyArrowPatch(
            (sx, y_start),
            (ex, y_end),
            arrowstyle="-|>",
            mutation_scale=14,
            linewidth=1.4,
            color=COLORS["arrow"],
            connectionstyle="arc3,rad=0.15",
            shrinkA=2,
            shrinkB=2,
        )
    ax.add_patch(path)
    if text:
        ax.text(
            (sx + ex) / 2 + text_offset[0],
            (y_start + y_end) / 2 + text_offset[1],
            text,
            ha="center",
            va="center",
            fontsize=9,
            color=COLORS["text"],
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="none", alpha=0.9),
        )


def build_diagram():
    fig, ax = plt.subplots(figsize=FIGSIZE)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 18)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    ax.text(
        7,
        17.35,
        "Dual-Signal Detector Flow",
        ha="center",
        va="center",
        fontsize=18,
        weight="bold",
        color=COLORS["text"],
    )
    ax.text(
        7,
        16.85,
        "Signal A z-score + Signal B collapse",
        ha="center",
        va="center",
        fontsize=11,
        color="#52606D",
    )

    start = add_box(
        ax,
        (7, 15.8),
        "New data point arrives\nSignal A + Signal B",
        5.2,
        1.0,
        COLORS["start"],
        fontsize=11,
        weight="bold",
    )
    phase = add_diamond(ax, (7, 14.0), "Still in\nlearning period?", 3.4, 1.2)

    learn = add_box(
        ax,
        (3.2, 11.8),
        "Learn Signal A baseline:\n• typical level (mean)\n• natural spread (std dev)",
        4.8,
        1.5,
        COLORS["process"],
    )
    learn_done = add_diamond(ax, (3.2, 9.6), "Learning period\ncomplete?", 3.0, 1.2)
    wait = add_box(ax, (3.2, 7.4), "No alert\n(still learning)", 3.4, 0.9, COLORS["ok"])
    lock = add_box(
        ax,
        (3.2, 5.8),
        "Lock Signal A spread (std dev)\nused later for all z-scores",
        4.8,
        1.1,
        COLORS["process"],
    )

    zscore = add_box(
        ax,
        (10.5, 11.8),
        "Compute z-score for Signal A:\n\nz = (value − mean) / locked std dev\n\nHow many typical spreads above normal?",
        5.4,
        2.0,
        COLORS["process"],
        fontsize=10,
    )
    zcheck = add_diamond(ax, (10.5, 9.3), "z > threshold?\n(e.g. z > 3.5)", 3.2, 1.2)
    collapse = add_diamond(ax, (10.5, 6.8), "B near zero?\n(0 ≤ B ≤ floor)", 3.2, 1.2)
    update = add_box(
        ax,
        (7.0, 4.6),
        "Normal point:\nupdate baseline mean only\n(spread stays locked)",
        4.8,
        1.2,
        COLORS["process"],
    )
    ok = add_box(ax, (4.5, 2.8), "No alert", 2.6, 0.8, COLORS["ok"], weight="bold")
    alert = add_box(
        ax,
        (11.5, 4.6),
        "Event detected\nspike in A + collapse in B",
        4.0,
        1.1,
        COLORS["alert"],
        weight="bold",
    )

    arrow(ax, start, phase)
    arrow(ax, phase, learn, "Yes", text_offset=(-0.8, 0.2))
    arrow(ax, learn, learn_done)
    arrow(ax, learn_done, wait, "Not yet", text_offset=(-0.9, 0.0))
    arrow(ax, learn_done, lock, "Yes", text_offset=(1.0, 0.0))
    arrow(ax, lock, wait)

    arrow(ax, phase, zscore, "No", text_offset=(0.8, 0.2))
    arrow(ax, zscore, zcheck)
    arrow(ax, zcheck, update, "No", text_offset=(-1.0, 0.0))
    arrow(ax, zcheck, collapse, "Yes")
    arrow(ax, collapse, update, "No", text_offset=(-0.8, 0.0))
    arrow(ax, collapse, alert, "Yes", text_offset=(0.8, 0.0))
    arrow(ax, update, ok)

    ax.text(
        0.55,
        0.55,
        "z-score measures how unusually high Signal A is, in units of locked spread.\n"
        "An event requires both a high z-score and Signal B collapse at the same time.",
        ha="left",
        va="bottom",
        fontsize=9.5,
        color="#52606D",
    )

    plt.tight_layout()
    return fig


def main():
    fig = build_diagram()
    png_path = f"{OUTPUT_BASE}.png"
    pdf_path = f"{OUTPUT_BASE}.pdf"

    fig.savefig(png_path, dpi=DPI, bbox_inches="tight", facecolor="white")
    with PdfPages(pdf_path) as pdf:
        pdf.savefig(fig, bbox_inches="tight", facecolor="white")

    plt.close(fig)
    print(f"Wrote {png_path}")
    print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
