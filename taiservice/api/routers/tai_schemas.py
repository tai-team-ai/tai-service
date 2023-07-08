"""Define the schemas for the TAI endpoints."""
from enum import Enum

class TaiTutorName(str, Enum):
    """Define the supported TAI tutors."""
    
    FIN = "fin"
    ALEX = "alex"
