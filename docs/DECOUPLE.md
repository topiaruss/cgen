# DECOUPLE.md

Frontend-Backend Decoupling Patterns for Kogarim

## Philosophy

**Templates should know NOTHING about the backend data model.** The view layer acts as a translator, converting model data into clean, UI-ready context variables.

## Anti-Patterns ❌

### Template Logic Based on Model Structure
```html
<!-- BAD: Template knows about model fields and values -->
{% if object.status == 'failed' %}
{% if object.brief.tasks.exists %}
{% if user.profile.subscription.is_premium %}
```

### Business Logic in Templates  
```html
<!-- BAD: Business logic in template -->
{% if task.created_at|timesince > "1 day" and task.status != "completed" %}
    <span class="overdue">Overdue!</span>
{% endif %}
```

### Template Tags with Business Logic
```python
# BAD: Template tag doing business logic
@register.filter
def task_is_overdue(task):
    return task.created_at < timezone.now() - timedelta(days=1) and task.status != 'completed'
```

## Good Patterns ✅

### View-Layer Data Transformation
```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    
    # Transform model data into UI-ready data
    generation = self.object
    
    # Status-based UI state (no model field exposure)
    context['is_completed'] = generation.status == 'completed'
    context['is_failed'] = generation.status == 'failed'
    context['show_retry_button'] = generation.can_retry()
    
    # Complex business logic resolved in view
    context['task_summary'] = {
        'total': generation.tasks.count(),
        'completed': generation.tasks.filter(status='completed').count(),
        'is_overdue': generation.is_overdue(),
        'next_action': generation.get_next_action_text()
    }
    
    return context
```

### Clean Template Usage
```html
<!-- GOOD: Template only knows about UI state -->
{% if is_completed %}
    <div class="success-state">Brief completed!</div>
{% endif %}

{% if show_retry_button %}
    <button class="retry-btn">Retry</button>
{% endif %}

<div class="task-summary">
    {{ task_summary.completed }} of {{ task_summary.total }} completed
    {% if task_summary.is_overdue %}
        <span class="overdue">{{ task_summary.next_action }}</span>
    {% endif %}
</div>
```

## Benefits

### 🔒 **Encapsulation**
- Templates can't accidentally access internal model fields
- Model refactoring doesn't break templates
- Database schema changes are isolated

### 🧪 **Testability**  
- Views can be unit tested with mock context data
- Template rendering can be tested independently
- Business logic is in testable Python code

### 🔄 **Maintainability**
- Single source of truth for UI logic in views
- Easy to change UI behavior without touching templates
- Clear separation of concerns

### 📱 **API Consistency**
- Same context transformation can be used for API responses
- Frontend and API return identical data structures
- Easy to add new output formats (JSON, XML, etc.)

## Implementation Patterns

### 1. Status-Based UI States
```python
# Instead of exposing status field
context['status'] = obj.status  # ❌

# Provide UI-specific boolean flags  
context['is_pending'] = obj.status == 'pending'     # ✅
context['is_processing'] = obj.status == 'processing' # ✅
context['can_edit'] = obj.is_editable_by(user)      # ✅
```

### 2. Pre-computed Display Data
```python
# Instead of raw model relationships
context['tasks'] = obj.tasks.all()  # ❌

# Provide structured display data
context['task_list'] = [
    {
        'id': task.pk,
        'title': task.get_display_title(),
        'status_class': f'status-{task.status}',
        'status_text': task.get_status_display(),
        'can_delete': task.can_delete_by(user),
        'progress_percent': task.get_progress_percentage()
    }
    for task in obj.tasks.all()
]  # ✅
```

### 3. Action Availability
```python
# Instead of complex template logic
# {% if user.is_staff or obj.created_by == user and obj.status != 'archived' %}

# Provide clear action flags
context['can_edit'] = obj.can_edit_by(user)
context['can_delete'] = obj.can_delete_by(user)  
context['can_archive'] = obj.can_archive_by(user)
context['show_admin_actions'] = user.is_staff and obj.allows_admin_actions()
```

### 4. Form Pre-population
```python
# Instead of passing model instances
context['selected_template'] = template_obj  # ❌

# Provide structured form data
context['form_data'] = {
    'selected_category': template_obj.category,
    'selected_template_id': template_obj.pk,
    'pre_filled_topic': template_obj.default_topic,
    'available_providers': obj.get_available_providers_for_user(user)
}  # ✅
```

## Migration Strategy

### Phase 1: New Views
- Apply decoupling pattern to all new views
- Use as reference implementation

### Phase 2: High-Traffic Views  
- Refactor views with heavy template logic
- Focus on performance-critical pages

### Phase 3: Systematic Cleanup
- Gradually migrate existing templates
- Remove unused template tags
- Consolidate business logic

## Code Review Checklist

- [ ] Does template access model fields directly? → Move to view
- [ ] Are there `if` statements with model values? → Convert to boolean flags  
- [ ] Is there business logic in template tags? → Move to model/service methods
- [ ] Would this template break if the model changed? → Add abstraction layer
- [ ] Can this template be tested without a database? → Improve context structure
- [ ] Does `make check-templates` pass? → Fix any line-break issues

## Examples in Codebase

✅ **Good Example**: `GenerationDetailView`
- Status checks moved to view (`is_completed`, `is_failed`)
- Task data pre-processed into display format
- Action availability pre-computed (`can_view_in_generator`)

❌ **Needs Refactoring**: Legacy views with `{% if object.field == 'value' %}` patterns

## Tools & Helpers

### Template Validation Tool
```bash
# Check for common template syntax issues
make check-templates

# Catches:
# - Incomplete template tags ({% without %})
# - Incomplete template variables ({{ without }})
# - Multi-line hx-vals with unmatched quotes
# - Include statements that may continue on next line
```

### Ruff Configuration for Templates
```toml
# Add to pyproject.toml to prevent ruff from breaking Django template tags
[tool.ruff.format]
exclude = [
    "**/*.html",
    "**/templates/**/*",
]
```

### Context Data Validation
```python
# Optional: Add context validation in development
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    
    # Your context transformations here...
    
    if settings.DEBUG:
        self._validate_context_structure(context)
    
    return context
```

### Testing Context Transformations
```python
def test_context_data_structure(self):
    """Test view provides expected UI-ready context."""
    view = MyDetailView()
    view.object = MyModel(status='completed')
    
    context = view.get_context_data()
    
    # Assert UI state, not model state
    assert context['is_completed'] is True
    assert 'task_list' in context
    assert all('status_class' in task for task in context['task_list'])
```

---

**Remember**: The template should be able to render with mock data that has no relationship to your actual models!
