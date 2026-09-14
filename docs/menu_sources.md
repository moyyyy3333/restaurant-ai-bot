# Demo menu sources

Snapshot generated **2026-09-07 21:09 UTC**.

## Method

No Turso/local secrets in this environment. Tokens come from public GitHub Actions Daily lead pipeline logs and Growth PR demo URLs, then each live `https://restaurant-ai-bot-two.vercel.app/demo/<token>` was fetched and parsed for `data-menu-source`. Transient 5xx/timeouts were retried. Early Austin pipeline tokens that 404 are leftover from a later database reset — they are unknown/missing, not classified as sample.

Classification:

- **REAL** — `data-menu-source` is `menu_page`, `order_page`, `social_photo`, `yelp`, or another non-sample source.
- **SAMPLE** — `data-menu-source=sample` (labeled sample prices).
- **UNKNOWN** — missing attribute, 404, or fetch/parse failure. Menus are not invented.

## Production census

- Public `/stats` sites (demo_sites rows): **420**
- Public `/stats` funnel.demos (leads with a token): **401**
- Rows classified in this snapshot: **86**
- Live pages with a menu attribute: **69**
- Production demos with no public token in this seed: **332** (re-run with Turso to list them)

Live `GET /demo/<token>` currently rebuilds the page. Enrich is fail-closed, so a later open can flip REAL to SAMPLE if Places/menu fetch fails. This snapshot records what each response contained. It does not invent dishes.

## Totals (this snapshot)

- **18 real**
- **51 sample**
- **17 unknown/missing**

## Growth pitch-pool tokens

Tokens named in PRs 9 / 12 / 14 / 16 (no separate pitch-pool file in the repo):

| name | city | category | demo_url | menu_source | notes |
| --- | --- | --- | --- | --- | --- |
| Apothecary Cafe & Wine Bar | Austin | cafe | https://restaurant-ai-bot-two.vercel.app/demo/01Gs2yIATAWL | SAMPLE | data-menu-source=sample — Wine by the glass, Bottle list, Espresso, Small plate — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Cream Parlor | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/QDfZzeoBRE9n | SAMPLE | data-menu-source=sample — House scoop, Sundae, Shake, Cone or cup — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Melange Creperie | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/M0KmfMqIbrEl | REAL | data-menu-source=menu_page — Andouille Sausage Crepe, Breakfast Taco Crepe, Roasted Veggie Salad, Pecan Salad — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Revolucion Coffee + Juice | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/1g3-F7WHHY8k | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Simply Phở | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/NlRkan5Pusto | SAMPLE | data-menu-source=sample — Phở đặc biệt, Phở gà, Bún, Spring rolls — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Thien An Sandwiches | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/EBMKiuowROVS | REAL | data-menu-source=menu_page — Banh Mi Ga, Banh Mi Cha Lua, Banh Mi Thit Jam, Banh Mi Tofu — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Via313 Pizzeria | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/XXswWW1VRlIB | SAMPLE | data-menu-source=sample — House pie, Pepperoni, White pie, Salad — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Yale Street Grill | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/wa2LGwK--aBb | SAMPLE | data-menu-source=sample — Breakfast plate, Pancakes or french toast, Breakfast taco or sandwich, Lunch plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |

## Demos

| name | city | category | demo_url | menu_source | notes |
| --- | --- | --- | --- | --- | --- |
| 1891 American Eatery and Bar | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/pZsrB8GI79A0 | SAMPLE | data-menu-source=sample — Kitchen plate, Lunch service, Supper, Sides — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Almost Famous | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/DofacFrFhz54 | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| American and Cuban coffee | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/sJ-mP2KnDIBn | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Antidote Coffee | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/yk04K6KX68CV | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Apothecary Cafe & Wine Bar | Austin | cafe | https://restaurant-ai-bot-two.vercel.app/demo/01Gs2yIATAWL | SAMPLE | data-menu-source=sample — Wine by the glass, Bottle list, Espresso, Small plate — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| ARCH Café | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/x7Y2bFAAgmfk | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| B&B Joint | Miami | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/6haIdu9tl9Pz | SAMPLE | data-menu-source=sample — Kitchen plate, Lunch service, Supper, Sides — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Bao'd Up |  |  | https://restaurant-ai-bot-two.vercel.app/demo/VvIhVSZHkCg9 | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Bianchini Mercato | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/O--RAyQIbY5y | REAL | data-menu-source=menu_page — Spiedino di Caprese, Rollatini di Mozzarella, Caprese Stracciatella Salad, Tartufo Salad — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Black Hole Coffee House | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/5i9Qrv3PLlkD | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Blue Lacy |  |  | https://restaurant-ai-bot-two.vercel.app/demo/u2jjsqsA7leB | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Bonjour Cafe | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/7qdviCOL8_nD | REAL | data-menu-source=menu_page — Nicoise, Salmon, Grilled Chicken, Caprese — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Cafe Galleria | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/A8bYXTkKE1Ot | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Chopsticks Express | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/zXADMT_yLjvi | REAL | data-menu-source=menu_page — Egg Roll, Shrimp Roll, Spring Roll (2), Chicken Teriyaki — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Chuy's |  |  | https://restaurant-ai-bot-two.vercel.app/demo/hgzM_wbTIjKl | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Cliff's Grill | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/Qk1NdQZI-j32 | SAMPLE | data-menu-source=sample — Breakfast plate, Pancakes or french toast, Breakfast taco or sandwich, Lunch plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Clos Bistro & Cafe | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/LwyD63hWc2Au | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| CoCo Fresh Tea & Juice | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/X2j-uxuIRJs2 | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Colleen's Kitchen |  |  | https://restaurant-ai-bot-two.vercel.app/demo/nGLcnkGCjNKk | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Conscious Cravings |  |  | https://restaurant-ai-bot-two.vercel.app/demo/uQTrDmllpefG | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Conscious Cravings | Austin | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/-ikz1E_rxPgp | SAMPLE | data-menu-source=sample — Grill, Catch, Pasta or grains, Share plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Cream Parlor | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/QDfZzeoBRE9n | SAMPLE | data-menu-source=sample — House scoop, Sundae, Shake, Cone or cup — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Cure Cafe | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/WYER5Kr_hL-K | REAL | data-menu-source=menu_page — Acai Bowl, Mango Bowl, Protein Waffles, Toast — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Dish Society |  |  | https://restaurant-ai-bot-two.vercel.app/demo/iDTCVws6hR6R | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Dish Society | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/rLb8FCOkUS6M | REAL | data-menu-source=menu_page — Brisket N' Eggs, Pork Belly Hash, Southwest Scramble, Southern Breakfast Skillet — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Double Trouble | Austin | cafe | https://restaurant-ai-bot-two.vercel.app/demo/b9vB_nN-m5gt | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| E Star Chinese Buffet |  |  | https://restaurant-ai-bot-two.vercel.app/demo/3dmomuSTkstD | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Eggman |  |  | https://restaurant-ai-bot-two.vercel.app/demo/1sYi46Z2z84D | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Elaine's Pork and Pie | Austin | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/3L8UGdBjVc5i | SAMPLE | data-menu-source=sample — Grill, Catch, Pasta or grains, Share plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Focaccia Bistro | Miami | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/DprFGmpmjPz8 | SAMPLE | data-menu-source=sample — Grill, Catch, Pasta or grains, Share plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Frenchies Dinner | Miami | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/bIO9ncQPL6S5 | SAMPLE | data-menu-source=sample — Kitchen plate, Lunch service, Supper, Sides — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Galloway's Sandwich Shop | Austin | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/byJ6FILpk4gW | SAMPLE | data-menu-source=sample — House sandwich, Hot sandwich, Cold cut, Soup — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Go Fish | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/1CEYJhz53TeH | REAL | data-menu-source=menu_page — Cucumber Salad, Spicy Crab Salad, Salmon Ring, Jalapeno Yellowfin — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| GVA BOX | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/ZoCmFLuIFi9Z | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| GW Gyro & Wings | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/lrwlM-PqbgwT | SAMPLE | data-menu-source=sample — Grill, Catch, Pasta or grains, Share plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Half Moon Empanadas | Miami | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/U5UbrUYNbnuP | REAL | data-menu-source=menu_page — Beef Empanada, Spicy Beef Empanada, Chicken Empanada, Spicy Chicken Empanada — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Harold's | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/6uHzUctF7gAz | SAMPLE | data-menu-source=sample — Kitchen plate, Lunch service, Supper, Sides — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Jenni's Noodle House | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/-zIJ-V-XOPvJ | SAMPLE | data-menu-source=sample — Kitchen plate, Lunch service, Supper, Sides — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Juan Valdez Café | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/GY4GRz7utQ3i | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Katz's | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/Urn-76MPxlyS | SAMPLE | data-menu-source=sample — Grill, Catch, Pasta or grains, Share plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Kerbey Lane Café |  |  | https://restaurant-ai-bot-two.vercel.app/demo/awQfMiVIg5at | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Koko Cafe | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/_NZTxd94xBOK | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Korea House | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/F1vDQauRYi-3 | SAMPLE | data-menu-source=sample — Kitchen plate, Lunch service, Supper, Sides — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| L'Oca d'Oro |  |  | https://restaurant-ai-bot-two.vercel.app/demo/2mzDCfq8THG7 | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| La Gazzetta | Miami | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/o_iG-fMMQeoY | REAL | data-menu-source=menu_page — Marinated Olives, Vitello Tonnato, Mozzarella Di Bufala, Polpette — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| La Moon | Miami | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/RTf2CbcCm4eA | SAMPLE | data-menu-source=sample — Grill, Catch, Pasta or grains, Share plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| La Pupusa Loca | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/ebJU-rKQa3Hd | REAL | data-menu-source=menu_page — Huevos, Frijol, Crema Y 2 Tortillas, Platano Maduro Y Crema, Huevos, Chorizos, Crema, Aguacate, Frijoles Y 2 Tortillas, Plato Tipico Salvadoreno — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Marufuku Ramen |  |  | https://restaurant-ai-bot-two.vercel.app/demo/RPkEJDhkQM2h | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Melange Creperie | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/M0KmfMqIbrEl | REAL | data-menu-source=menu_page — Andouille Sausage Crepe, Breakfast Taco Crepe, Roasted Veggie Salad, Pecan Salad — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Miami Under Ground | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/aEGN6bcLJZMl | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Mister Block Cafe | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/Gor72nWJNPKk | REAL | data-menu-source=menu_page — Caprese Salad, Tuna Salad, Caprese Sandwich, Ham and Cheese Sandwich — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Nando's |  |  | https://restaurant-ai-bot-two.vercel.app/demo/JkZc_BgGsS8S | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Orno Miami | Miami | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/5B1qhYeXKYRq | SAMPLE | data-menu-source=sample — Kitchen plate, Lunch service, Supper, Sides — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Pavón Coffee Den | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/3DLzbKSCJjo4 | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Petit Rouge | Miami | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/wl8ksbgZcabh | REAL | data-menu-source=menu_page — Soup du Jour, Salade Mesclun Maison, Classic Caesar Salad, Truite Grenobloise — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Pho I-10 | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/QriQmIUtMOiC | SAMPLE | data-menu-source=sample — Phở đặc biệt, Phở gà, Bún, Spring rolls — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Revolucion Coffee + Juice | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/1g3-F7WHHY8k | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Roland's Soul Food | Austin | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/NfWOw2F4zl2P | SAMPLE | data-menu-source=sample — Seasonal plates, Tonight's roast, Garden plate, Daily soup — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Rustica Hondureña | Miami | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/QzTEkSRkFTpI | SAMPLE | data-menu-source=sample — Seasonal plates, Tonight's roast, Garden plate, Daily soup — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Rustika Cafe & Bakery | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/sL7EkRvIUOdl | SAMPLE | data-menu-source=sample — Morning breads, Pastry case, Custom cakes, Cookies & slices — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Sam's BBQ | Austin | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/f_5hF9MciXcR | SAMPLE | data-menu-source=sample — Brisket, Ribs, Sausage, Sides — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Sharetea | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/MTg_A-cZltwo | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Simply Coffie | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/4EDfTorGlcKr | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Simply Phở | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/NlRkan5Pusto | SAMPLE | data-menu-source=sample — Phở đặc biệt, Phở gà, Bún, Spring rolls — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Tai Kee | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/rvR3yxAhb2wW | SAMPLE | data-menu-source=sample — Grill, Catch, Pasta or grains, Share plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Teapresso Bar | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/TAtKLRfrMwXz | REAL | data-menu-source=menu_page — Avocado Smoothie, Lava Flow Smoothie, Honeydew Slush, Mango Slush — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Teriyaki Kitchen | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/U8j7s0qOvMQU | REAL | data-menu-source=menu_page — Sweet & Sour Chicken or Pork, Mongolian Beef or Chicken, Broccoli Beef or Chicken, Kung Pao Chicken — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Texas Medical Center Commons | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/zLUSQZWrXGW2 | SAMPLE | data-menu-source=sample — Kitchen plate, Lunch service, Supper, Sides — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Texas Mesquite Grill |  |  | https://restaurant-ai-bot-two.vercel.app/demo/_4ur89DO-Ptd | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Thai Thani | Austin | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/rMWq8aJ_9VnR | REAL | data-menu-source=menu_page — Golden Triangles, Vegetable Rolls, Fried Tofu, Vegetable Tempura — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| The Original New Orleans Po-Boy and Gumbo Shop | Austin | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/ZNsitniK_uT3 | SAMPLE | data-menu-source=sample — Grill, Catch, Pasta or grains, Share plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| The Stone House |  |  | https://restaurant-ai-bot-two.vercel.app/demo/k7MG6MShdJPl | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| The Stone House | Austin | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/lXn9dLkZq87B | SAMPLE | data-menu-source=sample — Seasonal plates, Tonight's roast, Garden plate, Daily soup — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Thien An Sandwiches | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/EBMKiuowROVS | REAL | data-menu-source=menu_page — Banh Mi Ga, Banh Mi Cha Lua, Banh Mi Thit Jam, Banh Mi Tofu — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Think Tacos | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/ZoUXNca36__H | SAMPLE | data-menu-source=sample — Street tacos, Family platter, Salsa bar, Agua fresca — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Tout Suite | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/aKkUSX43uFkN | REAL | data-menu-source=menu_page — Breakfast Taco, Breakfast Croissant, The Classic, Bagel & Lox — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Uncle Bean's Coffee | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/IgWKVOofG3MJ | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Veracruz All Natural |  |  | https://restaurant-ai-bot-two.vercel.app/demo/T3-070410vPK | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Veracruz Fonda and Bar |  |  | https://restaurant-ai-bot-two.vercel.app/demo/S__Q_1RqQj0f | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Via313 Pizzeria | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/XXswWW1VRlIB | SAMPLE | data-menu-source=sample — House pie, Pepperoni, White pie, Salad — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Vietnam Restaurant | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/sui5P3BEhGQA | REAL | data-menu-source=menu_page — Shrimp with Beancurd Meatroll Vermicelli, Beef Stew Noodle soup, Curry Vermicelli with Choice of Chicken or Duck, Shrimp and Sour Soup — From their menu places.singleplatform.com — not sample prices. — known token (pipeline/PR) |
| Wild | Houston | cafe | https://restaurant-ai-bot-two.vercel.app/demo/8MwFoJpVXhCo | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Wynwood Cafe | Miami | cafe | https://restaurant-ai-bot-two.vercel.app/demo/ZJaV1FTYOBdo | SAMPLE | data-menu-source=sample — Espresso, Pour over, House drip, Fresh pastry — Sample prices — your real drinks replaces these. — known token (pipeline/PR) |
| Xian Sushi and Noodle - Mueller |  |  | https://restaurant-ai-bot-two.vercel.app/demo/d-SDqIrxr49O | UNKNOWN | demo missing (404) — http 404 — known token (pipeline/PR) |
| Yale Street Grill | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/wa2LGwK--aBb | SAMPLE | data-menu-source=sample — Breakfast plate, Pancakes or french toast, Breakfast taco or sandwich, Lunch plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
| Zapvor by Thai Spice | Houston | restaurant | https://restaurant-ai-bot-two.vercel.app/demo/1oUxyV9qBoYB | SAMPLE | data-menu-source=sample — Grill, Catch, Pasta or grains, Share plate — Sample prices — your real menu replaces these. — known token (pipeline/PR) |
