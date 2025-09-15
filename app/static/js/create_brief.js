// Create Brief Page JavaScript
// Auto-resize textarea
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('textarea').forEach(textarea => {
        textarea.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = this.scrollHeight + 'px';
        });
    });

    // JSON validation feedback
    const jsonField = document.getElementById('id_products_json');
    if (jsonField) {
        jsonField.addEventListener('input', function () {
            try {
                JSON.parse(this.value);
                this.classList.remove('is-invalid');
                this.classList.add('is-valid');
            } catch (e) {
                this.classList.remove('is-valid');
                this.classList.add('is-invalid');
            }
        });
    }
});

// Copy example data to form
function copyExampleToForm() {
    // Get example values
    const exampleTitle = document.getElementById('example-title').textContent;
    const exampleRegion = document.getElementById('example-region').textContent;
    const exampleAudience = document.getElementById('example-audience').textContent;
    const exampleMessage = document.getElementById('example-message').textContent;
    const exampleProducts = document.getElementById('example-products').textContent;
    const exampleAdditionalLanguages = document.getElementById('example-additional-languages');

    // Get form fields
    const titleField = document.getElementById('id_title');
    const regionField = document.getElementById('id_target_region');
    const audienceField = document.getElementById('id_target_audience');
    const messageField = document.getElementById('id_campaign_message');
    const productsField = document.getElementById('id_products_json');
    const primaryLanguageField = document.getElementById('id_primary_language');

    // Fill form fields
    if (titleField) titleField.value = exampleTitle;
    if (regionField) regionField.value = exampleRegion;
    if (audienceField) audienceField.value = exampleAudience;
    if (messageField) messageField.value = exampleMessage;
    if (productsField) productsField.value = exampleProducts.trim();

    // Set primary language to English (use the option with value for English)
    if (primaryLanguageField) {
        // Find the English language option
        const englishOption = primaryLanguageField.querySelector('option[value="1"]'); // English typically has ID 1
        if (englishOption) {
            primaryLanguageField.value = englishOption.value;
        }
    }

    // Handle additional languages checkboxes
    if (exampleAdditionalLanguages) {
        const languageIds = exampleAdditionalLanguages.getAttribute('data-language-ids');
        if (languageIds) {
            // First, uncheck all additional language checkboxes
            const allLanguageCheckboxes = document.querySelectorAll('input[name="additional_languages"]');
            allLanguageCheckboxes.forEach(checkbox => {
                checkbox.checked = false;
            });

            // Then check the example languages from data attribute
            const idsToCheck = languageIds.split(',');
            idsToCheck.forEach(id => {
                const checkbox = document.querySelector(`input[name="additional_languages"][value="${id.trim()}"]`);
                if (checkbox) {
                    checkbox.checked = true;
                }
            });
        }
    }

    // Trigger events for validation and auto-resize
    [titleField, regionField, audienceField, messageField, productsField, primaryLanguageField].forEach(field => {
        if (field) {
            field.dispatchEvent(new Event('input', { bubbles: true }));
            field.dispatchEvent(new Event('change', { bubbles: true }));

            // Auto-resize textareas
            if (field.tagName === 'TEXTAREA') {
                field.style.height = 'auto';
                field.style.height = field.scrollHeight + 'px';
            }
        }
    });

    // Show success feedback
    const button = document.querySelector('[data-testid="copy-example-btn"]');
    const originalText = button.innerHTML;
    const originalClass = button.className;

    button.innerHTML = '<i class="fas fa-check"></i> Copied!';
    button.className = 'btn btn-success btn-sm';

    // Scroll to top of form
    const cardHeader = document.querySelector('.card .card-header h4');
    if (cardHeader) {
        cardHeader.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
        });
    }

    // Reset button after 2 seconds
    setTimeout(() => {
        button.innerHTML = originalText;
        button.className = originalClass;
    }, 2000);
}

// Copy demo brief data to form
function copyDemoBriefToForm(demoBriefId) {
    // Get demo brief data from template (we'll embed it as JSON)
    const demoBriefData = window.demoBriefData[demoBriefId];
    if (!demoBriefData) {
        console.error('Demo brief data not found for ID:', demoBriefId);
        return;
    }

    // Fill form fields
    const titleField = document.querySelector('#id_title');
    const regionField = document.querySelector('#id_target_region');
    const audienceField = document.querySelector('#id_target_audience');
    const messageField = document.querySelector('#id_campaign_message');
    const productsField = document.querySelector('#id_products_json');
    const primaryLanguageField = document.querySelector('#id_primary_language');

    if (titleField) titleField.value = demoBriefData.title;
    if (regionField) regionField.value = demoBriefData.target_region;
    if (audienceField) audienceField.value = demoBriefData.target_audience;
    if (messageField) messageField.value = demoBriefData.campaign_message;
    if (productsField) productsField.value = JSON.stringify(demoBriefData.products, null, 2);
    if (primaryLanguageField) primaryLanguageField.value = demoBriefData.primary_language;

    // Handle additional languages checkboxes
    const allLanguageCheckboxes = document.querySelectorAll('input[name="additional_languages"]');
    allLanguageCheckboxes.forEach(checkbox => {
        checkbox.checked = demoBriefData.supported_languages.includes(parseInt(checkbox.value));
    });

    // Trigger events and resize textareas
    [titleField, regionField, audienceField, messageField, productsField, primaryLanguageField].forEach(field => {
        if (field) {
            field.dispatchEvent(new Event('input', { bubbles: true }));
            field.dispatchEvent(new Event('change', { bubbles: true }));
            if (field.tagName === 'TEXTAREA') {
                field.style.height = 'auto';
                field.style.height = field.scrollHeight + 'px';
            }
        }
    });

    // Scroll to form
    const cardHeader = document.querySelector('.card .card-header h4');
    if (cardHeader) {
        cardHeader.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    // Update example data section to show selected demo brief
    updateExampleDataDisplay(demoBriefData);

    // Show feedback
    const demoBriefCard = event.target.closest('.demo-brief-card');
    if (demoBriefCard) {
        const originalBg = demoBriefCard.style.backgroundColor;
        demoBriefCard.style.backgroundColor = '#d4edda';
        demoBriefCard.style.borderColor = '#28a745';
        setTimeout(() => {
            demoBriefCard.style.backgroundColor = originalBg;
            demoBriefCard.style.borderColor = '';
        }, 1500);
    }
}

// Update the example data section to display selected demo brief
function updateExampleDataDisplay(demoBriefData) {
    // Update example data elements
    const titleEl = document.getElementById('example-title');
    const regionEl = document.getElementById('example-region');
    const audienceEl = document.getElementById('example-audience');
    const messageEl = document.getElementById('example-message');
    const productsEl = document.getElementById('example-products');
    const primaryLangEl = document.getElementById('example-primary-language');
    const additionalLangsEl = document.getElementById('example-additional-languages');

    if (titleEl) titleEl.textContent = demoBriefData.title;
    if (regionEl) regionEl.textContent = demoBriefData.target_region;
    if (audienceEl) audienceEl.textContent = demoBriefData.target_audience;
    if (messageEl) messageEl.textContent = demoBriefData.campaign_message;

    // Format products JSON
    if (productsEl) {
        productsEl.textContent = JSON.stringify(demoBriefData.products, null, 2);
    }

    // Update primary language
    if (primaryLangEl) {
        const primaryLangOption = document.querySelector(`#id_primary_language option[value="${demoBriefData.primary_language}"]`);
        primaryLangEl.textContent = primaryLangOption ? primaryLangOption.textContent : 'English';
    }

    // Update additional languages display
    if (additionalLangsEl) {
        const langNames = [];
        const langCodes = [];
        demoBriefData.supported_languages.forEach(langId => {
            const langOption = document.querySelector(`input[name="additional_languages"][value="${langId}"]`);
            if (langOption) {
                const label = document.querySelector(`label[for="${langOption.id}"]`);
                if (label) {
                    langNames.push(label.textContent.trim());
                    // Extract language code from label (assumes format like "French (fr)")
                    const codeMatch = label.textContent.match(/\(([a-z]{2})\)/);
                    if (codeMatch) {
                        langCodes.push(codeMatch[1]);
                    }
                }
            }
        });

        additionalLangsEl.textContent = langNames.join(', ');
        // Update data attributes for the copy function
        additionalLangsEl.setAttribute('data-language-ids', demoBriefData.supported_languages.join(','));
        additionalLangsEl.setAttribute('data-language-codes', langCodes.join(','));
    }

    // Update the example section header to indicate it's from a demo brief
    const exampleHeader = document.querySelector('.card-header .mb-0');
    if (exampleHeader && exampleHeader.textContent.includes('💡 Example Brief Data')) {
        exampleHeader.innerHTML = '🎯 Selected Demo Brief Data';

        // Add a small reset button
        const resetBtn = document.getElementById('reset-example-btn');
        if (!resetBtn) {
            const resetButton = document.createElement('button');
            resetButton.type = 'button';
            resetButton.className = 'btn btn-outline-secondary btn-sm ms-2';
            resetButton.id = 'reset-example-btn';
            resetButton.innerHTML = '<i class="fas fa-undo"></i> Reset to Default';
            resetButton.onclick = resetExampleToDefault;
            exampleHeader.parentNode.appendChild(resetButton);
        }
    }
}

// Reset example data to default
function resetExampleToDefault() {
    // Restore original example data
    const titleEl = document.getElementById('example-title');
    const regionEl = document.getElementById('example-region');
    const audienceEl = document.getElementById('example-audience');
    const messageEl = document.getElementById('example-message');
    const productsEl = document.getElementById('example-products');
    const primaryLangEl = document.getElementById('example-primary-language');
    const additionalLangsEl = document.getElementById('example-additional-languages');

    if (titleEl) titleEl.textContent = 'Pacific Pulse Energy Drink Launch';
    if (regionEl) regionEl.textContent = 'Pacific Coast US/Mexico border cities';
    if (audienceEl) audienceEl.textContent = '18-30, urban, multilingual, health-conscious but fun-seeking';
    if (messageEl) messageEl.textContent = 'Natural energy that connects you to the coastal lifestyle';
    if (productsEl) {
        productsEl.textContent = `[
  {
    "name": "Pacific Pulse Original",
    "type": "Energy Drink"
  },
  {
    "name": "Pacific Pulse Zero",
    "type": "Sugar-Free Energy Drink"
  }
]`;
    }
    if (primaryLangEl) primaryLangEl.textContent = 'English';

    // Restore from original template data
    if (additionalLangsEl) {
        additionalLangsEl.textContent = 'French, German';
        // Restore data attributes from template values
        const templateLanguageIds = additionalLangsEl.getAttribute('data-template-language-ids');
        const templateLanguageCodes = additionalLangsEl.getAttribute('data-template-language-codes');
        if (templateLanguageIds) {
            additionalLangsEl.setAttribute('data-language-ids', templateLanguageIds);
        }
        if (templateLanguageCodes) {
            additionalLangsEl.setAttribute('data-language-codes', templateLanguageCodes);
        }
    }

    // Reset header
    const exampleHeader = document.querySelector('.card-header .mb-0');
    if (exampleHeader) {
        exampleHeader.innerHTML = '💡 Example Brief Data';
    }

    // Remove reset button
    const resetBtn = document.getElementById('reset-example-btn');
    if (resetBtn) {
        resetBtn.remove();
    }
}
