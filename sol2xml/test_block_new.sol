class Main : Object {
    run [ |
        b := Block new.
        s := (b isBlock) asString.
        _ := s print.
        _ := '\n' print.
        r := b value.
        s := (r isNil) asString.
        _ := s print.
    ]
}