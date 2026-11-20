import {
  comboboxClassNames,
  dropdownClassNames,
  fieldClassNames,
  inputClassNames,
  makeStaticStyles,
  selectClassNames,
  spinButtonClassNames,
  tabClassNames,
  textareaClassNames,
} from '@fluentui/react-components';
import { palette } from './orionTheme';

const f = `.${fieldClassNames.root}`;
const controls = [
  inputClassNames.root,
  selectClassNames.root,
  textareaClassNames.root,
  comboboxClassNames.root,
  dropdownClassNames.root,
  spinButtonClassNames.root,
]
  .map((c) => `${f} .${c}`)
  .join(', ');

/** Site-wide static CSS. Fluent v9 Field is a one-column grid and its controls keep
 * min-width:auto, so a long option made them overflow into the next column. Every control inside
 * a Field now shrinks (min-width:0) and never exceeds its cell. */
const useStaticStyles = makeStaticStyles({
  '*, *::before, *::after': { boxSizing: 'border-box' },
  'html, body, #root': { margin: 0, padding: 0 },
  body: { backgroundColor: palette.canvas, overflowX: 'hidden' },
  'img, video': { maxWidth: '100%' },
  [f]: { minWidth: 0, gridTemplateColumns: 'minmax(0, 1fr)' },
  [controls]: { minWidth: 0, maxWidth: '100%' },
  [`${f} .${selectClassNames.select}`]: { minWidth: 0, textOverflow: 'ellipsis' },
  [`${f} .${inputClassNames.input}, ${f} .${comboboxClassNames.input}`]: { minWidth: 0 },
  [`${f} .${dropdownClassNames.button}`]: { minWidth: 0, overflow: 'hidden' },
  [`${f} .${textareaClassNames.textarea}`]: { minWidth: 0 },
  // Selected tab: strong text + a 3 px yellow indicator (the state is also shown by weight).
  [`.${tabClassNames.root}[aria-selected='true']::after`]: {
    backgroundColor: `${palette.yellow} !important`,
  },
  [`[aria-orientation='horizontal'] > .${tabClassNames.root}[aria-selected='true']::after`]: {
    height: '3px !important',
  },
  [`[aria-orientation='vertical'] > .${tabClassNames.root}[aria-selected='true']::after`]: {
    width: '3px !important',
  },
  [`.${tabClassNames.root}[aria-selected='true']`]: { fontWeight: 600 },
});

/** Renders nothing; mounts the static styles once, inside the FluentProvider. */
export function GlobalStyles() {
  useStaticStyles();
  return null;
}
