# Poise

**Poise** in **[Dark Souls 3](/Dark+Souls+3+Wiki "Dark Souls 3 Wiki") **affects the effectiveness of Hyper Armor, which allows players to perform attacks without being interrupted by enemy hits. High Poise is crucial for wielding powerful and heavy weapons, as it enables you to execute strong attacks more smoothly and with less risk of being staggered by enemy strikes. This makes Poise an important stat for maintaining offensive momentum and successfully landing powerful blows during combat. There are two in-game concepts called **Poise** in **[Dark Souls 3](/Dark+Souls+3+Wiki "Dark Souls 3 Wiki")**.

  * Poise, also known as "armor poise," is a stat that helps determine how well a player can maintain their attacks without being interrupted. Poise can be increased by equipping certain pieces of armor, such as those worn by Lothric Knights, using weapons like the [Lothric Knight Long Spear](/Lothric+Knight+Long+Spear "Dark Souls 3 Lothric Knight Long Spear"), or carrying shields like [Yhorm's Greatshield](/Yhorm's+Greatshield "Dark Souls 3 Yhorm's Greatshield"). Additionally, the [Wolf Ring](/Wolf+Ring "Dark Souls 3 Wolf Ring") also boosts Poise. The maximum achievable Poise ranges from 50.15 to 67.22, depending on the combination of gear and items used.
  * There is a hidden value called "poise health," which ranges from 100 to 0, and determines how long your "hyperarmor frames" last before being interrupted. The visible Poise stat serves as a defense for this poise health by reducing the amount of poise damage inflicted by enemy attacks. Essentially, a higher Poise stat helps you maintain your hyperarmor frames longer, allowing you to complete powerful attacks without being staggered.

The stagger resistance provided by skills such as [Unfaltering Prayer](/Unfaltering+Prayer "Dark Souls 3 Unfaltering Prayer"), [Perseverance](/Perseverance "Dark Souls 3 Perseverance"), [Stone Flesh](/Stone+Flesh "Dark Souls 3 Stone Flesh"), and the pyromancy [Iron Flesh](/Iron+Flesh "Dark Souls 3 Iron Flesh") operates independently of the player's Poise stat. These abilities each have their own separate "poise health," which determines their effectiveness against interruptions. Notably, the Great Hammer version of [Perseverance](/Perseverance "Dark Souls 3 Perseverance") does interact with the player's Poise stat, meaning it can activate the player's poise and help resist staggering effects during its use.

> The ability to withstand attacks without breaking form 

## How Poise Works in Dark Souls 3

In a nutshell, **the Poise stat (aka armor poise) reduce the poise damage taken by hits by that number percentage, still if you don't attack or attack with "small and fast weapons" you will be no matter what stunned** , you are only able to resist stagger during attacks with "hyperarmor" frames (Ultra Greatswords, Great Hammers, 2 handed Greatswords and certain WA ), and your Poise stat determines how many attacks you can take before you can be staggered out of hyperarmor frames. Because hyperarmor frames are not fully uninterruptible and use Poise to determine whether or not you can be interrupted, it would be more accurate to call them "active poise". In the game's code, the supposedly deactivated value for poise is in fact activated during animations with active poise.

All characters using the player model, including the player character, most NPCs, and non-player invaders, have a hidden poise health of 100. All attacks that hit the character will reduce this value, and when the value reaches 0 the character will be staggered regardless of whether or not they are in the middle of an attack with poise frames. The stat Poise will reduce how much poise damage a weapon inflicts to this poise health, by a percentage equal to the amount of Poise. Your Poise stat is always passively reducing incoming poise damage, whether or not you are using an attack with active poise. However, you are only able to resist stagger during active poise, and at any other time you can be staggered regardless of how much poise health you have left.

Furthermore, all attacks and actions with active poise will give a multiplier to your current poise health (usually negative), allowing you to take more or fewer hits before being staggered. The modifiers for normal R1 and R2 attacks on weapons with active poise were greatly reduced in the 1.08 patch, to the point where characters need very high poise to resist stagger from one or two attacks now. However, as of the 1.08 patch, attacks with active poise will now automatically refresh your poise health back to 80% of full after modifiers. For example, if you are using a Greataxe weapon (maximum poise health for R1 is 27) and you have 0.1 poise health before the attack, then as soon as your attack starts your poise will instantly reset to 21.6. What this means is you can now resist stagger from one or two attacks every time you attack, which allows tanky, high poise builds to play much more aggressively. Weapon arts with active poise have much higher modifiers than normal attacks do, being anywhere from 0.30 to 2.00 vs 0.10 to 0.27, and weapon arts will refresh your poise health back to 100% of full instead of 80%. Attacks that are blocked by a shield do not reduce your poise health at all.

Your poise health does not regenerate, but will immediately refresh back to 100% every 30 seconds or when it's reduced to 0, whichever comes first. In addition, the 1.08 patch made it so that your poise health resets to 80% of full whenever you use a normal attack with active poise and to 100% of its full value whenever you use a weapon art with active poise.

To use poise, you need to know these things: how much poise damage your opponent's attacks deal, what the poise health of your attacks is, and how much Poise from armor you need to reduce your opponent's poise damage far enough to not drop your poise health to zero. In addition, since your poise health resets back to 80% with every normal attack, it would also be helpful to have enough poise so that 20.01% of your poise health is left over, as this will allow you to resist stagger through your opponent's attack every time you attack. For weapons that only have active poise during their weapon arts, this is less important since weapon arts reset poise health back to 100% instead of 80%.

Active poise is found on certain weapon attacks including, but not limited to, Ultra Greatsword, Greathammer, and Greataxe R1s, Greatsword two-handed R1s, fully charged R2 attacks, most Weapon Skills, and the medium and heavy rolls. The 1.08 patch also gave active poise to two-handed Hammer attacks. Testing is still ongoing to determine which attacks have poise frames and what their poise multipliers are.

### Stat Poise Information in Dark Souls 3

Each piece of armor has a Poise rating, and your total Poise is the sum of each of your armor pieces. Naked characters have 0 Poise. In general, wearing heavier or more protective armor increases Poise.

The max poise armor is Havel set with 50.15, with Wolf Ring+3 and Yhorm Greatshield the poise is 61.44 and also equipping Lothric spear will give you the maximum possible of 67.45.

As of patch 1.07. the Poise formula seems to reduce the effects of poise for armor and rings added once the player has any poise. Every piece added that increases poise will be subjected to the following formula:

α + β - [(α x β ) / 100] α= Current total poise value β= New armor/ring piece poise value

So if adding the [Wolf Ring](/Wolf+Ring "Dark Souls 3 Wolf Ring")+3 (9 poise) on a character with 10 poise:

10 + 9 - [(10 x 9) / 100] =**18.1**

### Weapons Poise Damage in Dark Souls 3

If you wanna know the poise value of other attack just multiply :

**1h R2 & 2h R1 **by**1,3;** **1h fullR2 & 2h R2 **by**1,55;** **2h fullR2** by**1,65; Run, backstep, jump 1h, 2h attack** by**1.1** &**1.4 (Run) Dual L1** by**0,8 per hit Roll Dual L1** by**0,7 per hit**

Poise damage 1hR1 | Weapons   
---|---  
3, 5 or 7  | [Bows](/Bows "Dark Souls 3 Bows"), [Crossbows](/Crossbows "Dark Souls 3 Crossbows")*, most lesser Sorceries  
10 | [Daggers](/Daggers "Dark Souls 3 Daggers"), Torch, most Throwing Items, some Miracles   
11 |  Thrusting swords, Caestus  
14 | Straight Swords, Curved Swords, Katanas, Axes, Spears, Pikes, Reapers, Whips, Claws & Fists, Pyromancy Flame, Bare fists, Staves, most Sorcereries  
19 |  [Reinforced Club](/Reinforced+Club "Dark Souls 3 Reinforced Club"), Halberds, most Pyromancy  
25 | Hammers, [Follower Torch](/Follower+Torch "Dark Souls 3 Follower Torch"), Small Shields, Great Chaos Orb  
26 | [ Greatswords](/Greatswords "Dark Souls 3 Greatswords"), Standard Shields  
27 | (Great)Heavy Soul Arrow, (Crystal)Souls Spears, Souls Greatswords  
30 | Lifehunt Scythe, Dead Again, Black Fire Orb  
31 | [Ultra Greatswords](/Ultra+Greatswords "Dark Souls 3 Ultra Greatswords"), [Curved Greatswords](/Curved+Greatswords "Dark Souls 3 Curved Greatswords"), Greataxes,[ ](/Curse+Ward+Greatshield "Dark Souls 3 Curse Ward Greatshield")[Greatshields](/Greatshields "Dark Souls 3 Greatshields")  
35 |  Great Hammers, Greatbows*  
40 | Dark Edge, Boulder Heave,   
  
*Avelyn halves the single value, Headshot deals 1,5 times more (ex. 5 does 7,5)

*Dragonslayer Arrow have knockdown

### Enemies Stance, Stagger & Riposte in Dark Souls 3

[Entities](/Enemies "Dark Souls 3 Enemies") have their own poise, depleting it will stagger them (some of them may let you riposte them), if you do not hit them for **10 second** they will **instantly refill** their poise.

DO NOT CONFUSE **Poise-break Riposte** with**Weak Spot-break Riposte** or with **C ounterattack riposte,**

The first critical is triggered by bring the enemies poise to 0 with enough hit, the second one is triggered by dealing enough damage (20%-45% enemy's HP, no timer reset) to the creature's weak spot (usually the head) and the third one is triggered by hitting the creature at its right attack moment.

#### ENEMIES & MINI BOSSES

Poise Health |   
---|---  
0 | Mostly human type enemies, Rats, Dog, Skeletons, Follower, Corvian-  Millwood- Ringed - and Harald Knights, Centipede, Ghru, Slug, Thrall, ecc...  
35 | Silver Knight  
45 | Fat Deacon  
60 | Demon Cleric, Irithill Small Giant  
62 | Boreal Beast Knight*, Evangelist*, Great Snakeman  
75 | DarkWraith*, Mimic  
80 | Headless Gargoyle  
85 | Black Knight, Fat (Winged) Lothric Knight  
90 | Deep Accursed, Tree Woman  
95 | Cathedral Crusader   
110 | Elder Ghru, Lothric Gargoyle  
115 | Ravenous lizard  
120 | Fire Demon  
140 | Sullyvan Dog Beast, Great Crab (double claw slam)  
∞ | Cathedral Big Giant, Pus of Man, Monstrosity of Sin (grab)  
  
*Heavy hitstun will always stagger them

#### BOSSES

Poise Health |   
---|---  
0 | Friede, Crystal Sage   
98 | Gael (1st phase also instastaggered by knowdowns, 2nd phase by headshot, instastunned when he pulls out crossbow )  
120 | Oceiros, Fire Demon  
150 | Sulyvahn  
170 | Boreal Dancer , Demon King, Gravetender Wolf, Soul of Cinder (some of his attack will weaken him to poise damage by 1.5)  
185 | Gundyr  
200 | Vordt (during breath)  
210 | Twin Princess, Demon Princes (the body in 2nd phase has poise damage reduction to 0.9)  
215 | Nameless King  
250 | Ariandel (shares poise with Friede)  
260 | Stray Demon  
300 | Dragonslayer Armor (dont confuse with 2nd phase stagger)  
350 | Yhorm  
∞ | Greatwood, Wolnir, Aldrich, King of the Storm, Midir  
  
Video Source: Bosses poise comparison - Dark Souls 3

### PVE Poise Damage Dark Souls 3

Usually [enemies](/Enemies "Dark Souls 3 Enemies") tend to do from 15 to 45 for fast attack and 70 to 130 for strong attack and 5 for spell and arrow , this are poise damage value while having 0 armor poise (being naked or wearing stripes) , equipping armor reduce the poise damage by that percentage (Ex. 30 armor poise reduce eneny poise damage by 30% , so an attack of 30 PM will be reduce to 21 PM). 

The max poise is Havel set with 50.15, with Wolf Ring+3 and Yhorm Greatshield the max poise is 61.44 and also equipping Lothric spear will give you 67.45.

**Enemy** | **Poise Damage**  
---|---  
[Champion Gundyr](/Champion+Gundyr "Dark Souls 3 Champion Gundyr") | 

  * Fast attacks 10, 12, 15, 20, 25
  * Strong attacks 70

  
[Vordt of the Boreal Valley](/Vordt+of+the+Boreal+Valley "Dark Souls 3 Vordt of the Boreal Valley") | 

  * Fast attacks 45, 55
  * Strong attacks & charge 70

  
[Deacons of the Deep](/Deacons+of+the+Deep "Dark Souls 3 Deacons of the Deep") | 

  * Candlestick 15
  * Fire orb 25

  
[Abyss Watchers](/Abyss+Watchers "Dark Souls 3 Abyss Watchers") | 

  * All slash 25
  * Knife 5
  * 50 Slam
  * 25 Flames

  
[Pontiff Sulyvahn](/Pontiff+Sulyvahn "Dark Souls 3 Pontiff Sulyvahn") | 

  * Paired slash 15
  * Single slash 30

  
[Aldrich, Devourer of Gods](/Aldrich,+Devourer+of+Gods "Dark Souls 3 Aldrich, Devourer of Gods") | 

  * Projectiles 12 , 30, 35

  
[Old Demon King](/Old+Demon+King "Dark Souls 3 Old Demon King") | 

  * 25, 30 ,50 Fire Ring
  * 70 meteor

  
Yhorm the Giant | 

  * Always 30

  
[Dancer of the Boreal Valley](/Dancer+of+the+Boreal+Valley "Dark Souls 3 Dancer of the Boreal Valley") | 

  * 25; 30, 45 ; 70

  
[Oceiros, the Consumed King](/Oceiros,+the+Consumed+King "Dark Souls 3 Oceiros, the Consumed King") | 

  * 35 ; 70

  
[Dragonslayer Armour](/Dragonslayer+Armour "Dark Souls 3 Dragonslayer Armour") | 

  * 30 ; 70

  
[Soul of Cinder](/Soul+of+Cinder "Dark Souls 3 Soul of Cinder") | 

  * Every move has different value 45, 12, 20, 25, 30. 55 ,70 ,100
  * Magic 10, 30, 45

  
[Nameless King](/Nameless+King "Dark Souls 3 Nameless King") | 

  * Main slashes 55, 70
  * Minor slashes 10, 15

  
[Sister Friede](/Sister+Friede "Dark Souls 3 Sister Friede") | 

  * 15, 25
  * Ice 30
  * Slam 55
  * 70
  * Black flame 130

  
[Slave Knight Gael](/Slave+Knight+Gael "Dark Souls 3 Slave Knight Gael") | 

  * 1st phase 15, grab 45
  * 2nd phase 20+5 mantle ,explosion 50, lighting 0

  
Darkeater Midir | 

  * 130, fire n laser 999

  
LORIAN.: 30 ; 70 LOTHRIC.: projectile 30 ; small orbs 10 x hit  
  
### Dark Souls 3 Poise Notes, Tips & Trivia

For a long time, it was believed that the poise stat either didn't work or was intentionally disabled on release, due to a player finding a value in the game's code that determined whether or not poise was active and seeing that the value was 'off' by default. It was later discovered by other people that this value was only turned on during what was thought to be hyperarmor frames at the time, and that poise damage is constantly being calculated at all times but you are only able to resist stagger during attacks or actions with hyperarmor frames.

Boulder Heave is unique among spells in that it also inflicts poise damage. If an opponent is struck by the debris, it will deal a large amount of poise damage. However, spells and skills that cause knockdown do not take poise into account.

Enemies that do not use the player model, such as Darkwraiths, Silver Knights, and Black Knights, do not follow the same rules for poise that the player character and NPCs do.

[Stats](/Stats "Dark Souls 3 Stats")  
---  
[Attunement](//darksouls3.wiki.fextralife.com/Attunement) ♦ [Bleed](//darksouls3.wiki.fextralife.com/Bleed) ♦ [Curse](//darksouls3.wiki.fextralife.com/Curse) ♦ [Dark Defense](//darksouls3.wiki.fextralife.com/Dark+Defense) ♦ [Dexterity](//darksouls3.wiki.fextralife.com/Dexterity) ♦ [Endurance](//darksouls3.wiki.fextralife.com/Endurance) ♦ [Equipment Load](//darksouls3.wiki.fextralife.com/Equipment+Load) ♦ [Faith](//darksouls3.wiki.fextralife.com/Faith) ♦ [Fire Defense](//darksouls3.wiki.fextralife.com/Fire+Defense) ♦ [FP](//darksouls3.wiki.fextralife.com/FP) ♦ [Frostbite](//darksouls3.wiki.fextralife.com/Frostbite) ♦ [Intelligence](//darksouls3.wiki.fextralife.com/Intelligence) ♦ [Item Discovery](//darksouls3.wiki.fextralife.com/Item+Discovery) ♦ [Lightning Defense](//darksouls3.wiki.fextralife.com/Lightning+Defense) ♦ [Luck](//darksouls3.wiki.fextralife.com/Luck) ♦ [Magic Defense](//darksouls3.wiki.fextralife.com/Magic+Defense) ♦ [Physical Defense](//darksouls3.wiki.fextralife.com/Physical+Defense) ♦ [Poison](//darksouls3.wiki.fextralife.com/Poison) ♦ [Strength](//darksouls3.wiki.fextralife.com/Strength) ♦ [Vigor](//darksouls3.wiki.fextralife.com/Vigor) ♦ [Vitality](//darksouls3.wiki.fextralife.com/Vitality)
