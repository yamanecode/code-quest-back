from sqlalchemy import delete, exists, or_, select
from sqlalchemy.orm import Session

from app.domain.enums import ContentStatus
from app.infra.db.models import Challenge, ClassroomMember, Mission, MissionChallenge, Submission

PUBLISHED = ContentStatus.PUBLISHED


class MissionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        title: str,
        position: int,
        classroom_id: int | None = None,
        description: str | None = None,
        status: ContentStatus = ContentStatus.DRAFT,
    ) -> Mission:
        mission = Mission(
            title=title,
            position=position,
            classroom_id=classroom_id,
            description=description,
            status=status,
        )
        self.session.add(mission)
        self.session.flush()
        return mission

    def get(self, mission_id: int) -> Mission | None:
        return self.session.get(Mission, mission_id)

    def get_base_by_title(self, title: str) -> Mission | None:
        query = select(Mission).where(Mission.classroom_id.is_(None), Mission.title == title)
        return self.session.scalar(query)

    def list_base(self) -> list[Mission]:
        query = select(Mission).where(Mission.classroom_id.is_(None))
        return list(self.session.scalars(query.order_by(Mission.position, Mission.id)))

    def list_for_classroom(self, classroom_id: int) -> list[Mission]:
        query = select(Mission).where(Mission.classroom_id == classroom_id)
        return list(self.session.scalars(query.order_by(Mission.position, Mission.id)))

    def delete(self, mission: Mission) -> None:
        self.session.delete(mission)
        self.session.flush()

    def set_challenges(self, mission_id: int, challenge_ids: list[int]) -> None:
        """Replace the mission's challenges; the list order becomes the mission order."""
        self.session.execute(
            delete(MissionChallenge).where(MissionChallenge.mission_id == mission_id)
        )
        for position, challenge_id in enumerate(challenge_ids):
            link = MissionChallenge(
                mission_id=mission_id, challenge_id=challenge_id, position=position
            )
            self.session.add(link)
        self.session.flush()

    def challenge_ids(self, mission_id: int) -> list[int]:
        query = (
            select(MissionChallenge.challenge_id)
            .where(MissionChallenge.mission_id == mission_id)
            .order_by(MissionChallenge.position, MissionChallenge.id)
        )
        return list(self.session.scalars(query))

    def has_published_challenge(self, mission_id: int) -> bool:
        condition = (
            exists()
            .where(MissionChallenge.mission_id == mission_id)
            .where(MissionChallenge.challenge_id == Challenge.id)
            .where(Challenge.status == PUBLISHED)
        )
        return bool(self.session.scalar(select(condition)))

    def has_submissions(self, mission_id: int) -> bool:
        mission_challenges = select(MissionChallenge.challenge_id).where(
            MissionChallenge.mission_id == mission_id
        )
        query = select(exists().where(Submission.challenge_id.in_(mission_challenges)))
        return bool(self.session.scalar(query))

    def _visible_missions(self, user_id: int):
        member_classrooms = select(ClassroomMember.classroom_id).where(
            ClassroomMember.user_id == user_id
        )
        return select(Mission.id).where(
            Mission.status == PUBLISHED,
            or_(Mission.classroom_id.is_(None), Mission.classroom_id.in_(member_classrooms)),
        )

    def visible_mission_ids(self, user_id: int) -> set[int]:
        """Published base missions plus published missions of the student's turmas."""
        return set(self.session.scalars(self._visible_missions(user_id)))

    def visible_published_challenge_ids(self, user_id: int) -> set[int]:
        query = (
            select(MissionChallenge.challenge_id)
            .join(Challenge, Challenge.id == MissionChallenge.challenge_id)
            .where(
                Challenge.status == PUBLISHED,
                MissionChallenge.mission_id.in_(self._visible_missions(user_id)),
            )
            .distinct()
        )
        return set(self.session.scalars(query))
