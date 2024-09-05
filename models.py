from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URI = "sqlite:///podcasts.db"  # Database location
engine = create_engine(DATABASE_URI)
Base = declarative_base()
Session = sessionmaker(bind=engine)
session = Session()

class ShowProfile(Base):
    __tablename__ = 'show_profiles'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    host1 = Column(String)
    host1_voice = Column(String)
    host1_personality = Column(String)
    host2 = Column(String)
    host2_voice = Column(String)
    host2_personality = Column(String)
    host3 = Column(String)
    host3_voice = Column(String)
    host3_personality = Column(String)
    scripts = relationship("Script", back_populates="show")

class Podcast(Base):
    __tablename__ = 'podcasts'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    host1 = Column(String)
    host2 = Column(String)
    host3 = Column(String)
    research = Column(String)
    scripts = relationship("Script", back_populates="podcast")

class Script(Base):
    __tablename__ = 'scripts'
    id = Column(Integer, primary_key=True)
    content = Column(String)
    audio = Column(String)
    research_url = Column(String)  # Add this line
    show_id = Column(Integer, ForeignKey('show_profiles.id'))
    podcast_id = Column(Integer, ForeignKey('podcasts.id'))  # Add this line
    show = relationship("ShowProfile", back_populates="scripts")
    podcast = relationship("Podcast", back_populates="scripts")

# Create the tables if they don't exist
Base.metadata.create_all(engine)