class Main : Object {
    run [ |
        a := nil.
        b := nil.

        x := (a identicalTo: b) asString.    _ := x print.
        _ := '\n' print.
        x := (a identicalTo: nil) asString.  _ := x print.
        _ := '\n' print.

        "Nil new vraci stale stejnou instanci nil"
        c := Nil new.
        x := (c identicalTo: nil) asString.  _ := x print.
        _ := '\n' print.

        "from: taky"
        d := Nil from: nil.
        x := (d identicalTo: nil) asString.  _ := x print.
    ]
}