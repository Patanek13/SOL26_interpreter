# Nástroj pro integrační testování – TypeScript

> [!NOTE]
> Platí zde všechny obecné instrukce pro řešení v jazyce TypeScript, které jsou 
> uvedeny v `README.md` v nadřazeném adresáři.

Při implementaci nástroje pro integrační testování máte v zásadě volnou ruku. K dispozici máte předpřipravenou kostru s načítáním parametrů z příkazové řádky, kterou můžete libovolně upravit.

## Struktura projektu

- `package.json`: projektový soubor, definuje především závislosti (knihovny).
- `package-lock.lock`: automaticky generovaný „lockfile“, do kterého npm uvádí konkrétní verze knihoven,
  které stáhl (slouží pro reprodukovatelnost).
- `eslint.config.mjs` a `prettier.config.mjs`: konfigurační soubory pro nástroje ESLint a Prettier.
- `tsconfig.json`: konfigurační soubor pro překladač TypeScriptu.
- `src/tester.ts`: vstupní skript, připravený kód pro parsování argumentů příkazové řádky a inicializaci
  logování. Tento skript můžete rovnou dále rozšiřovat.
- `src/models.ts`: definice datových struktur (modelů), které reprezentují jak samotný načtený test, tak i 
  výstupní report. Všechny modely jsou zde podrobně popsány.

Příklad spuštění:

```bash
npm start -- --help
# případně
npm run build
node ./dist/tester.js --help
```

## Možnosti úpravy šablony

**Povinně** musíte využít modely definované v modulu `models.ts`. Zde najdete třídy, které reprezentují
načtený test (`TestCaseDefinition`) i výstupní report (`TestReport`). Modely neměňte (pokud by to
z nějakého důvodu pro vás bylo nezbytné, konzultujte to na fóru). Zejména z modelu `TestCaseDefinition`
však můžete dědit ve vlastním modelu, který bude obsahovat další atributy.

Můžete (a nemusíte) využít také model `TestCaseDefinitionFile`, který reprezentuje pouze „objevený soubor
s testem“. `TestCaseDefinition` z něj pak dědí (reprezentuje objevený _a rozparsovaný_ soubor).

Mimo tyto modely je řešení **zcela na vás** – poskytnutý soubor `tester.ts` nemusíte vůbec využít.
Důležité je pouze to, aby parametry příkazové řádky odpovídaly zadání. (Použití dodaných modelů
zajišťuje správnost výstupního formátu.)

## Spouštění v kontejneru a interakce s dalšími nástroji

Není specifikován konkrétní způsob, jakým váš testovací nástroj spustí překladač SOL2XML a váš 
interpret. Cesty k překladači a interpretu tedy v podstatě mohou být i napevno definované ve vašem 
kódu, ačkoliv to není považováno za vhodné řešení. Doporučujeme raději použít proměnné prostředí, 
konfigurační soubor nebo vlastní parametry příkazové řádky.

Povinně podporované parametry příkazové řádky jsou popsány v zadání.

## Návratové kódy

Testovací nástroj podporuje pouze následující chybové návratové kódy:
- 1: Zadaná cesta k adresáři s testy neexistuje nebo není adresářem.
- 2: Neplatné argumenty (např. chybějící povinné argumenty, neznámé argumenty atd.).

V nástroji jinak neexistuje žádný „očekávaný“ chybový stav. V případě neočekávaných chyb při
spouštění jednotlivých testů se záznam o této chybě projeví v reportu (vizte model `UnexecutedReason`),
ale testovací nástroj by měl i tak provést všechny testy a skončit s návratovým kódem 0.