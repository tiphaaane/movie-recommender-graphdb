from typing import Literal
from pydantic import BaseModel, Field
class MovieSuggestion(BaseModel):
    movie_id:int=Field(gt=0)
    title:str=Field(min_length=1)
    score:float=Field(ge=0,le=1)
    reason:str=Field(min_length=1)
class MovieRecommendations(BaseModel):
    movie_id:int
    recommendations:list[MovieSuggestion]
    data_source: Literal['mock','movielens','neo4j']='mock'
class UserRecommendations(BaseModel):
    user_id:int
    recommendations:list[MovieSuggestion]
    data_source: Literal['mock','movielens','neo4j']='mock'
class TrendingMovies(BaseModel):
    movies:list[MovieSuggestion]
    data_source: Literal['mock','movielens','neo4j']='mock'
