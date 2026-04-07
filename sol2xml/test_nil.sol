class Main : Object {
    run [ |
        n := nil.
        _ := (n asString) print.
        _ := '\n' print.

        x := (n isNil) asString.
        _ := x print.
        _ := '\n' print.

        "nil je jedinavek - identicalTo: vraci true"
        same := n identicalTo: nil.
        _ := (same asString) print.
    ]
}