"""Built-in problem library, grouped by logic domain.

`expected` is the correct SZS answer; the test-suite runs every installed
prover on every example and checks that no prover ever contradicts it.
"""

EXAMPLES: list[dict[str, str]] = [
    # ------------------------------------------------------- propositional
    {
        "id": "prop-modus-ponens",
        "domain": "Propositional logic",
        "title": "Modus ponens",
        "description": "From p and p => q, conclude q.",
        "expected": "Theorem",
        "source": """fof(premise, axiom, p).
fof(rule, axiom, p => q).
fof(goal, conjecture, q).
""",
    },
    {
        "id": "prop-de-morgan",
        "domain": "Propositional logic",
        "title": "De Morgan's law",
        "description": "Negation of a conjunction is the disjunction of negations.",
        "expected": "Theorem",
        "source": """fof(de_morgan, conjecture, ~ (p & q) <=> (~ p | ~ q)).
""",
    },
    {
        "id": "prop-affirming-consequent",
        "domain": "Propositional logic",
        "title": "Affirming the consequent (a fallacy)",
        "description": "From p => q and q, p does NOT follow. Provers should find a counter-model.",
        "expected": "CounterSatisfiable",
        "source": """fof(rule, axiom, p => q).
fof(observation, axiom, q).
fof(goal, conjecture, p).
""",
    },
    # -------------------------------------------------------- first-order
    {
        "id": "fol-socrates",
        "domain": "First-order logic",
        "title": "Socrates is mortal",
        "description": "The classic syllogism.",
        "expected": "Theorem",
        "source": """fof(all_men_mortal, axiom, ![X]: (man(X) => mortal(X))).
fof(socrates_man, axiom, man(socrates)).
fof(socrates_mortal, conjecture, mortal(socrates)).
""",
    },
    {
        "id": "fol-drinker",
        "domain": "First-order logic",
        "title": "Drinker paradox",
        "description": "There is someone such that, if they drink, everyone drinks.",
        "expected": "Theorem",
        "source": """fof(drinker, conjecture, ?[X]: (drinks(X) => ![Y]: drinks(Y))).
""",
    },
    {
        "id": "fol-quantifier-swap",
        "domain": "First-order logic",
        "title": "Quantifier swap is not valid",
        "description": "Everyone loves someone does not mean someone is loved by everyone.",
        "expected": "CounterSatisfiable",
        "source": """fof(everyone_loves_someone, axiom, ![X]: ?[Y]: loves(X, Y)).
fof(someone_loved_by_all, conjecture, ?[Y]: ![X]: loves(X, Y)).
""",
    },
    {
        "id": "fol-cnf-refutation",
        "domain": "First-order logic",
        "title": "Clause-form refutation (CNF)",
        "description": "A small set of clauses with the goal already negated.",
        "expected": "Unsatisfiable",
        "source": """cnf(parent_ancestor, axiom, ~ parent(X, Y) | ancestor(X, Y)).
cnf(transitive, axiom, ~ ancestor(X, Y) | ~ ancestor(Y, Z) | ancestor(X, Z)).
cnf(p1, axiom, parent(alice, bob)).
cnf(p2, axiom, parent(bob, carol)).
cnf(goal, negated_conjecture, ~ ancestor(alice, carol)).
""",
    },
    # ---------------------------------------------------------- equational
    {
        "id": "eq-group-commutative",
        "domain": "Equational logic (group theory)",
        "title": "Groups of exponent 2 are commutative",
        "description": "If x*x = e for every x, the group is abelian.",
        "expected": "Theorem",
        "source": """fof(left_identity, axiom, ![X]: mult(e, X) = X).
fof(left_inverse, axiom, ![X]: mult(inv(X), X) = e).
fof(associativity, axiom, ![X, Y, Z]: mult(mult(X, Y), Z) = mult(X, mult(Y, Z))).
fof(exponent_two, axiom, ![X]: mult(X, X) = e).
fof(commutativity, conjecture, ![X, Y]: mult(X, Y) = mult(Y, X)).
""",
    },
    {
        "id": "eq-right-identity",
        "domain": "Equational logic (group theory)",
        "title": "Left identity implies right identity",
        "description": "In a group axiomatised from the left, e is also a right identity.",
        "expected": "Theorem",
        "source": """fof(left_identity, axiom, ![X]: mult(e, X) = X).
fof(left_inverse, axiom, ![X]: mult(inv(X), X) = e).
fof(associativity, axiom, ![X, Y, Z]: mult(mult(X, Y), Z) = mult(X, mult(Y, Z))).
fof(right_identity, conjecture, ![X]: mult(X, e) = X).
""",
    },
    {
        "id": "eq-not-commutative",
        "domain": "Equational logic (group theory)",
        "title": "Groups need not be commutative",
        "description": "The group axioms alone do not imply commutativity.",
        "expected": "CounterSatisfiable",
        "source": """fof(left_identity, axiom, ![X]: mult(e, X) = X).
fof(left_inverse, axiom, ![X]: mult(inv(X), X) = e).
fof(associativity, axiom, ![X, Y, Z]: mult(mult(X, Y), Z) = mult(X, mult(Y, Z))).
fof(commutativity, conjecture, ![X, Y]: mult(X, Y) = mult(Y, X)).
""",
    },
    # ---------------------------------------------------------- set theory
    {
        "id": "set-subset-transitive",
        "domain": "Set theory",
        "title": "Subset is transitive",
        "description": "Using the definition of subset via membership.",
        "expected": "Theorem",
        "source": """fof(subset_def, axiom, ![A, B]: (subset(A, B) <=> ![X]: (member(X, A) => member(X, B)))).
fof(transitivity, conjecture, ![A, B, C]: ((subset(A, B) & subset(B, C)) => subset(A, C))).
""",
    },
    {
        "id": "set-intersection-commutes",
        "domain": "Set theory",
        "title": "Intersection is commutative",
        "description": "With extensionality, A ∩ B = B ∩ A.",
        "expected": "Theorem",
        "source": """fof(extensionality, axiom, ![A, B]: ((![X]: (member(X, A) <=> member(X, B))) => A = B)).
fof(intersection_def, axiom, ![X, A, B]: (member(X, intersection(A, B)) <=> (member(X, A) & member(X, B)))).
fof(commutes, conjecture, ![A, B]: intersection(A, B) = intersection(B, A)).
""",
    },
]

_BY_ID = {example["id"]: example for example in EXAMPLES}


def get_example(example_id: str) -> dict[str, str] | None:
    return _BY_ID.get(example_id)
