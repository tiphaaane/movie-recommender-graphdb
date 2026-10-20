"""Run recommender methods against a local MovieLens Small copy."""
from app.recommendations.service import MovieRecommender

if __name__ == "__main__":
    model = MovieRecommender("data/ml-latest-small")
    print("Popular:", model.trending(5))
    print("Similar to Toy Story:", model.similar_movies(1, 5))
    print("For user 1:", model.user_recommendations(1, 5))
