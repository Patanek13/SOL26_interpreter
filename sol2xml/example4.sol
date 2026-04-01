class Parent : Object {
  something [|
    "definuje a inicializuje instanční atributy 'p' a 'q'"
    p := self p: 'hello'.
    q := self q: 'world'.
    "Je-li příjemce instance Parent, získá hodnotu v 'p' a vytiskne 'hello'."
    "Je-li příjemce instance Main, reaguje invokací metody 'p' a vypíše 'foo'."
    _ := (self p) print. ]
}

class Main : Parent {
  run [|
    "tyto čtyři příkazy mají stejný efekt"
    a := super value: super. b := super value: self.
    c := self value: super. d := self value: self.

    x := self p: 'val'. "CHYBA 54! Vedlo by na vznik atributu, ale už máme instanční metodu p, takže atribut nelze vytvořit."
    x := self p. "hodnotou x bude 'foo'"

    x := super something: 1. "CHYBA 54! Vedlo by na vznik atributu, ale v nadtřídě je kolizní metoda."
    x := super p. "CHYBA 51! Nadtřída nezná selektor p. (something se zatím neprovedla)"

    _ := super something. "nastaví atributy p, q a vypíše 'foo'"
    x := self p. "x = 'foo' (volání metody)"
    y := super p. "y = 'hello' (přístup k atributu)"
    z := self q. "q = 'world' (přístup k atributu)"
  ]

  p [|
    "instanční metoda, která jen vrátí řetězec 'foo'"
    _ := 'foo'.
  ]
}
