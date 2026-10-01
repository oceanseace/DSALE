/**
 * Tuş ipucu: "O" · "Shift+O" · "Esc". Dokunmatik ekranda gizlenir (klavye
 * yokken tuş öğretmek gürültüdür).
 */

import './bilesen.css';

export function Kbd({ children }: { children: string }) {
  const parcalar = children.split('+');
  return (
    <span className="o-kbd" aria-hidden="true">
      {parcalar.map((p, i) => (
        <kbd key={i}>{p}</kbd>
      ))}
    </span>
  );
}
