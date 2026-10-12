#!/bin/sh
# Generates the 10 job sheets (5 front + 5 back, 4 characters each) via PixelLab MCP. 1 credit each.
F="2x2 sprite sheet of four separate cute chibi fantasy RPG characters with identical chibi proportions (big head, small body, small dot eyes), short messy dark brown hair, each centered in its own quarter with empty space between them, full body, standing, front view facing the viewer."
B="2x2 sprite sheet of four separate cute chibi fantasy RPG characters with identical chibi proportions (big head, small body), short messy dark brown hair, each centered in its own quarter with empty space between them, full body, seen from behind, three-quarter back view, battle ready stance facing away from the viewer."
E="pixel art game sprites, dark navy outline, basic shading"
J1="top-left: boy warrior in simple leather armor holding a broadsword. top-right: boy archer in a green hooded tunic with a short bow and quiver. bottom-left: boy thief with a dark scarf over his mouth, light leather and a dagger. bottom-right: boy healer in a white and blue robe holding a wooden staff with a holy symbol."
J2="top-left: boy mage in a purple robe and pointed hat holding a staff with a glowing orb. top-right: boy knight in heavy plate armor carrying a huge two-handed greatsword. bottom-left: boy knight in plate armor with a kite shield and a one-handed longsword. bottom-right: boy knight riding a small armored pony, holding a lance."
J3="top-left: boy trapper archer with goggles, bear traps hanging on his belt and a small crossbow. top-right: boy ranger with an elegant longbow, feathered cap and green cape. bottom-left: boy assassin in a dark hood holding two daggers. bottom-right: boy ninja thief throwing shuriken, dark outfit and headband."
J4="top-left: girl dancer with flowing veils and silk scarves holding a curved dagger. top-right: boy priest in a white and gold robe with a mitre hat and holy staff. bottom-left: boy monk martial artist in a gi with wrapped fists and prayer beads. bottom-right: boy wizard with a big wide brimmed hat, spellbook and glowing staff."
J5="top-left: boy elementalist with small fire and water spirits floating around him. top-right: girl novice adventurer in a plain white sleeveless undershirt and brown shorts, barefoot, short bob hair. bottom-left: girl priestess in a white and gold robe with a holy staff. bottom-right: girl archer in a green hooded tunic with a short bow."
i=1
for J in "$J1" "$J2" "$J3" "$J4" "$J5"; do
  python3 -I tools/mcp_pixflux.py assets/raw/jobs/front$i.png 128 128 south "$F $J $E" $((600+i)) || exit 1
  python3 -I tools/mcp_pixflux.py assets/raw/jobs/back$i.png 128 128 north-east "$B $J $E" $((700+i)) || exit 1
  i=$((i+1))
done
