# Register your models here.
from django.contrib import admin
from .models import Course, Question, StudentProfile, Quiz, QuizAttempt, TeacherProfile, Assignment, Note, ResearchPaper, TeacherSubjectContent

class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user_username', 'user_email', 'phone', 'department')

    def user_username(self, obj):
        return obj.user.username

    def user_email(self, obj):
        return obj.user.email

class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user_username', 'courses_count')

    def user_username(self, obj):
        return obj.user.username

    def courses_count(self, obj):
        return obj.courses.count()

class ResearchPaperAdmin(admin.ModelAdmin):
    list_display = ('title', 'authors', 'journal', 'published_date', 'uploaded_at')
    list_filter = ('published_date', 'journal')
    search_fields = ('title', 'authors', 'journal', 'doi')

class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'total_questions', 'total_marks', 'time_limit', 'created_at')
    list_filter = ('course', 'created_at')
    search_fields = ('title', 'course__title')

admin.site.register(Course)
admin.site.register(Question)
admin.site.register(StudentProfile, StudentProfileAdmin)
admin.site.register(Quiz, QuizAdmin)
admin.site.register(QuizAttempt)
admin.site.register(TeacherProfile, TeacherProfileAdmin)
admin.site.register(Assignment)
admin.site.register(Note)
admin.site.register(ResearchPaper, ResearchPaperAdmin)
admin.site.register(TeacherSubjectContent)
