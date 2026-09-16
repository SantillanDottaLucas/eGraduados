from django.db import models
from django.utils import tree

# Create your models here.

class Graduado(models.Model):
    legajoGraduado = models.CharField(max_length=14, primary_key=True)
    dniGraduado = models.CharField(max_length=9, unique=True)
    fechaNacimiento= models.DateField()
    
