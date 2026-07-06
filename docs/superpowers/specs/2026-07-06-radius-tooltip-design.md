# Radius Tooltip Design

## Goal

Explain the checkpoint radius with a small Russian tooltip beside its label.

## Design

Place a focusable `ⓘ` icon immediately after
`Радиус контрольной точки (м)`. Show this text on mouse hover and keyboard
focus:

> Расстояние, в пределах которого точка считается пройденной.

Implement the tooltip with HTML and CSS only. Associate the explanation with
the icon through an accessible label. Do not change the radius input or form
behavior.

## Testing

Extend the home-page rendering test to verify the icon, Russian explanation,
and focusability. Run the focused home-page test and the existing web tests.
