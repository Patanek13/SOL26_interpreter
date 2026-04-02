class Factorial : Integer {
factorial "použití from: pro podtřídu třídy Integer"
[| r := (self equalTo: 0) ifTrue: [|r := Factorial from: 1.]
ifFalse: [|r := self multiplyBy:
((Factorial from: (self plus: -1)) factorial). ].
]
}

class Main : Object {
run
[| x := Factorial from: ((String read) asInteger).
x := ((x factorial) asString) print.
"CHYBA 53! Factorial dědí z Integer, tudíž obsahuje interní instanční
atribut s číselnou hodnotou - řetězec takový interní atribut nemá"
y := Factorial from: 'str'.
]
}
