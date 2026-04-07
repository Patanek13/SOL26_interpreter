class Main : Object {
    run [ |
        t1 := true.
        t2 := true.
        f1 := false.
        f2 := false.

        x := (t1 identicalTo: t2) asString. _ := x print.
        _ := '\n' print.
        x := (f1 identicalTo: f2) asString. _ := x print.
        _ := '\n' print.
        x := (t1 identicalTo: f1) asString. _ := x print.
        _ := '\n' print.

        "Vysledek not je stale jedinavek"
        x := ((true not) identicalTo: false) asString. _ := x print.
        _ := '\n' print.
        x := ((false not) identicalTo: true) asString. _ := x print.
    ]
}