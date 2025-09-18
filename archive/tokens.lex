# literals
integer:        \d+(_\d+)*([eE][+-]?\d+(_\d+)*)?(?!\.)
float:          \d+(_\d+)*)?\.\d+(_\d+)*([eE][+-]?\d+(_\d+)*)?

# operators
operator:       [+\-*/^%]

# basics
NAME:           [a-zA-Z_][a-zA-Z0-9_]*
COLON:          :
ASSIGN:         =

LBRACE:         \{
RBRACE:         \}

WHITESPACE:     \s+
