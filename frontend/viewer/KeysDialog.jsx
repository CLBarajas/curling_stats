/* The keyboard's shortcuts, on one card (2026-11-20): from the keyboard
 * button beside the playback gear, or `?`. A page opened to watch lists only
 * what watching uses; one that can chart lists the charting keys as well.
 * Not on a tablet, which has no keyboard to speak of.
 *
 * The video's keys are the ones YouTube's player answers, so a hand that
 * knows YouTube already knows them. The page has to answer them itself:
 * YouTube's frame is handed the keyboard back the moment it is clicked
 * (runtime/player.mjs, keepKeys), and the page's own <video> has no keys. */
import { useEffect, useRef } from "react";
import { STONE_NAME } from "../core/constants.mjs";
import { CLOSE } from "./DeliveryDialog.jsx";

/* j and l move the video this far, as on YouTube; Shift with an arrow, this. */
export const JUMP_SEEK_S = 10;
export const SHIFT_SEEK_S = 5;
/* Keys that switch something on and off: a held key fires them once. */
export const TOGGLE_KEYS = ["k", "p", " ", "m", "f", "t"];

export const KEYS_ICON = (
  <svg width="18" height="16" viewBox="0 0 26 20" fill="none" stroke="currentColor" strokeWidth={2}
       strokeLinecap="round" aria-hidden="true">
    <rect x="1.5" y="2" width="23" height="16" rx="3" />
    <path d="M6 7h.01M10 7h.01M14 7h.01M18 7h.01M6 11h.01M10 11h.01M14 11h.01M18 11h.01M8.5 14.5h9" />
  </svg>
);

/* [keys, what they do]: each key a <kbd>; a group's rows in the order a
 * person reaches for them. */
const ESC = [["Esc"], "Close it, or the report or the playback settings"];

function groups(readOnly) {
  const watch = [
    ["Rocks", [
      [["←", "→"], "Previous or next rock in this end"],
      [["v"], "Back to the start of this rock in the video"],
      [["t"], "Show or hide the rock's track"],
    ]],
    ["Video", [
      [["k", "Space"], "Play or pause (p does too)"],
      [["j", "l"], `Back or forward ${JUMP_SEEK_S} seconds`],
      [["Shift ←", "Shift →"], `Back or forward ${SHIFT_SEEK_S} seconds`],
      [["m"], "Sound on or off"],
      [["f"], "Full screen, or back"],
    ]],
  ];
  if (readOnly) return [...watch, ["This card", [[["?"], "Open it"], ESC]]];
  return [
    ...watch,
    ["Charting", [
      [["Enter"], "Mark this rock charted and go to the next one to chart"],
      [["n"], "Next rock still to chart"],
      [["0", "4"], "Score this rock, 0 to 4"],
      [["r", "y"], `Stones you add are ${STONE_NAME.red.toLowerCase()} or ${STONE_NAME.yellow.toLowerCase()}`],
      [["x"], "Delete the selected stone"],
      [["c"], "Change the selected stone's colour"],
      [["d"], "The selected stone is the one delivered"],
    ]],
    ["This card", [[["?"], "Open it"], ESC]],
  ];
}

/* "←" "→" read as a pair; "0" "4" as a range. */
function Keys({ keys }) {
  const joint = keys.length === 2 && keys[0] === "0" ? " to " : " / ";
  return keys.map((k, i) => (
    <span key={k}>{i ? joint : null}<kbd>{k}</kbd></span>
  ));
}

export function KeysDialog({ open, readOnly, onClose }) {
  const ref = useRef(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  // A click on the backdrop lands on the <dialog> itself; anything inside the
  // padded wrapper does not.
  const onClick = e => { if (e.target === e.currentTarget) e.currentTarget.close(); };
  return (
    <dialog id="keysDialog" ref={ref} onClose={onClose} onClick={onClick} aria-labelledby="keysTitle">
      {open ? (
        <div className="dd-body">
          <div className="dd-head">
            <h2 id="keysTitle">Keyboard shortcuts</h2>
            <span className="grow" />
            <span className="dd-esc">Esc to close</span>
            <form method="dialog"><button className="dd-close" aria-label="Close">{CLOSE}</button></form>
          </div>
          <div className="kd-groups">
            {groups(readOnly).map(([title, rows]) => (
              <section key={title}>
                <h3>{title}</h3>
                <dl>
                  {rows.map(([keys, what]) => (
                    <div key={what} className="kd-row">
                      <dt><Keys keys={keys} /></dt>
                      <dd>{what}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            ))}
          </div>
        </div>
      ) : null}
    </dialog>
  );
}
