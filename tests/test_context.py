"""Phase 1.7 — ContextBuilder test suite.

Validates the Context dataclass and ContextBuilder's true delta
computation (d_c = C(t) - C(t-1)), replacing the old absolute-value
pass-through in luna.py.
"""

from __future__ import annotations

import pytest

from luna_common.consciousness.context import Context, ContextBuilder
from luna_common.schemas import InfoGradient


class TestContext:
    """Validate the Context dataclass."""

    def test_context_dataclass(self):
        """Context stores 4 float values accessible by name."""
        ctx = Context(
            memory_health=0.8,
            phi_quality=0.6,
            phi_iit=0.4,
            output_quality=0.9,
        )
        assert ctx.memory_health == 0.8
        assert ctx.phi_quality == 0.6
        assert ctx.phi_iit == 0.4
        assert ctx.output_quality == 0.9


class TestContextBuilder:
    """Validate ContextBuilder: stateful delta computation."""

    def test_builder_first_step_uses_bootstrap(self):
        """First step: delta = current - 0.5 (bootstrap default).

        Default C(t-1) = (0.5, 0.5, 0.5, 0.5).
        Input (0.8, 0.6, 0.4, 0.9) produces deltas (0.3, 0.1, -0.1, 0.4).
        """
        builder = ContextBuilder()
        grad = builder.build(
            memory_health=0.8,
            phi_quality=0.6,
            phi_iit=0.4,
            output_quality=0.9,
        )
        assert grad.delta_mem == pytest.approx(0.3, abs=1e-10)
        assert grad.delta_phi == pytest.approx(0.1, abs=1e-10)
        assert grad.delta_iit == pytest.approx(-0.1, abs=1e-10)
        assert grad.delta_out == pytest.approx(0.4, abs=1e-10)

    def test_builder_second_step_computes_delta(self):
        """Second step: delta = C(t) - C(t-1), not C(t) - bootstrap.

        Step 1: (0.8, 0.6, 0.4, 0.9)
        Step 2: (0.9, 0.7, 0.5, 0.8) -> deltas = (0.1, 0.1, 0.1, -0.1)
        """
        builder = ContextBuilder()
        builder.build(
            memory_health=0.8,
            phi_quality=0.6,
            phi_iit=0.4,
            output_quality=0.9,
        )
        grad = builder.build(
            memory_health=0.9,
            phi_quality=0.7,
            phi_iit=0.5,
            output_quality=0.8,
        )
        assert grad.delta_mem == pytest.approx(0.1, abs=1e-10)
        assert grad.delta_phi == pytest.approx(0.1, abs=1e-10)
        assert grad.delta_iit == pytest.approx(0.1, abs=1e-10)
        assert grad.delta_out == pytest.approx(-0.1, abs=1e-10)

    def test_builder_stable_input_zero_delta(self):
        """Same input twice produces delta ~ 0 on the second call."""
        builder = ContextBuilder()
        builder.build(
            memory_health=0.7,
            phi_quality=0.7,
            phi_iit=0.7,
            output_quality=0.7,
        )
        grad = builder.build(
            memory_health=0.7,
            phi_quality=0.7,
            phi_iit=0.7,
            output_quality=0.7,
        )
        assert grad.delta_mem == pytest.approx(0.0, abs=1e-10)
        assert grad.delta_phi == pytest.approx(0.0, abs=1e-10)
        assert grad.delta_iit == pytest.approx(0.0, abs=1e-10)
        assert grad.delta_out == pytest.approx(0.0, abs=1e-10)

    def test_builder_returns_info_gradient(self):
        """build() returns an InfoGradient instance."""
        builder = ContextBuilder()
        result = builder.build(
            memory_health=0.5,
            phi_quality=0.5,
            phi_iit=0.5,
            output_quality=0.5,
        )
        assert isinstance(result, InfoGradient)

    def test_builder_custom_initial(self):
        """Custom initial context is respected.

        initial=(0, 0, 0, 0), input=(0.3, 0.4, 0.5, 0.6)
        -> deltas = (0.3, 0.4, 0.5, 0.6)
        """
        builder = ContextBuilder(
            initial=Context(
                memory_health=0.0,
                phi_quality=0.0,
                phi_iit=0.0,
                output_quality=0.0,
            )
        )
        grad = builder.build(
            memory_health=0.3,
            phi_quality=0.4,
            phi_iit=0.5,
            output_quality=0.6,
        )
        assert grad.delta_mem == pytest.approx(0.3, abs=1e-10)
        assert grad.delta_phi == pytest.approx(0.4, abs=1e-10)
        assert grad.delta_iit == pytest.approx(0.5, abs=1e-10)
        assert grad.delta_out == pytest.approx(0.6, abs=1e-10)

    def test_builder_negative_deltas(self):
        """Score decreasing produces negative deltas."""
        builder = ContextBuilder()
        builder.build(
            memory_health=0.9,
            phi_quality=0.8,
            phi_iit=0.7,
            output_quality=0.9,
        )
        grad = builder.build(
            memory_health=0.3,
            phi_quality=0.2,
            phi_iit=0.1,
            output_quality=0.4,
        )
        assert grad.delta_mem == pytest.approx(-0.6, abs=1e-10)
        assert grad.delta_phi == pytest.approx(-0.6, abs=1e-10)
        assert grad.delta_iit == pytest.approx(-0.6, abs=1e-10)
        assert grad.delta_out == pytest.approx(-0.5, abs=1e-10)

    def test_builder_previous_property(self):
        """.previous returns the last context after build()."""
        builder = ContextBuilder()
        builder.build(
            memory_health=0.8,
            phi_quality=0.6,
            phi_iit=0.4,
            output_quality=0.9,
        )
        prev = builder.previous
        assert prev.memory_health == pytest.approx(0.8, abs=1e-10)
        assert prev.phi_quality == pytest.approx(0.6, abs=1e-10)
        assert prev.phi_iit == pytest.approx(0.4, abs=1e-10)
        assert prev.output_quality == pytest.approx(0.9, abs=1e-10)

    def test_builder_integration_with_evolution(self):
        """ContextBuilder output feeds into evolve() without error.

        Smoke test: build() -> as_list() -> evolve() preserves simplex.
        """
        import numpy as np
        from luna.consciousness.state import ConsciousnessState

        builder = ContextBuilder()
        grad = builder.build(
            memory_health=0.7,
            phi_quality=0.6,
            phi_iit=0.3,
            output_quality=0.8,
        )

        cs = ConsciousnessState(agent_name="LUNA")
        psi_others = [
            np.array([0.50, 0.10, 0.15, 0.25]),
            np.array([0.10, 0.15, 0.50, 0.25]),
            np.array([0.25, 0.10, 0.15, 0.50]),
        ]
        new_psi = cs.evolve(psi_others, info_deltas=grad.as_list())

        # Simplex preserved: all >= 0 and sum ~= 1.0
        assert np.all(new_psi >= -1e-10)
        assert abs(new_psi.sum() - 1.0) < 0.01

    def test_builder_bounds_within_info_gradient(self):
        """Deltas stay within InfoGradient bounds [-10, 10].

        Since inputs are typically [0, 1], deltas are in [-1, 1],
        well within the [-10, 10] bounds.
        """
        builder = ContextBuilder(
            initial=Context(
                memory_health=1.0,
                phi_quality=1.0,
                phi_iit=1.0,
                output_quality=1.0,
            )
        )
        grad = builder.build(
            memory_health=0.0,
            phi_quality=0.0,
            phi_iit=0.0,
            output_quality=0.0,
        )
        # Worst case: delta = -1.0, well within [-10, 10]
        for delta in grad.as_list():
            assert -10.0 <= delta <= 10.0
