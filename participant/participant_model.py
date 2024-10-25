from typing import Optional, List

from grisera import BasicParticipantOut, BasicParticipantStateOut


class BasicParticipantOutToMongo(BasicParticipantOut):
    participant_states: Optional[List[BasicParticipantStateOut]]
