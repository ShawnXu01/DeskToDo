from deskcal.ui.onboarding.guided_tour import TOUR_STEPS


def test_guided_tour_is_short_and_has_unique_steps():
    assert 3 <= len(TOUR_STEPS) <= 7
    assert len({step.key for step in TOUR_STEPS}) == len(TOUR_STEPS)
    assert all(len(step.body) <= 65 for step in TOUR_STEPS)


def test_schedule_step_can_be_skipped_when_component_is_hidden():
    schedule = next(step for step in TOUR_STEPS if step.key == "schedule")
    assert schedule.target_key == "schedule"
    assert schedule.skip_if_missing is True
