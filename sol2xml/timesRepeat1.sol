class Main : Object {
    run [|
        x := 1.
        _ := 5 timesRepeat: [ :i |
            x := x multiplyBy: 2.
        ].
        a := x asString.
        _ := a print.
        _ := '\n' print.
    ]
}