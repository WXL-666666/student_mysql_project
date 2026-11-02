import factory
from models import Student

class StudentFactory(factory.Factory):
    class Meta:
        model = Student
    name = factory.Sequence(lambda n: f"Student {n}")   
    age = factory.Faker("random_int", min=0, max=100)
    grade = factory.Faker("random_element", elements=["A","B","C","D"])


