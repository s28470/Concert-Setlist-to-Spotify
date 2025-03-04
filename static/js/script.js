function addUrlField() {
    const container = document.getElementById('urlFieldsContainer');
  
    // Create a container for the new field
    const fieldContainer = document.createElement('div');
    fieldContainer.classList.add('field-container');
  
    // Create an input for the URL
    const newUrlField = document.createElement('input');
    newUrlField.type = 'url';
    newUrlField.name = 'url';
    newUrlField.required = true;
    newUrlField.placeholder = 'Setlist.fm URL';
    newUrlField.classList.add('url-field');
  
    // Create the delete button
    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.classList.add('delete-url-button');
    deleteButton.textContent = 'X';
    deleteButton.addEventListener('click', function() {
      container.removeChild(fieldContainer);
    });
  
    // Append the input and delete button to the field container
    fieldContainer.appendChild(newUrlField);
    fieldContainer.appendChild(deleteButton);
  
    // Append the field container to the main container
    container.appendChild(fieldContainer);
  }
  
  function removeField(button) {
    const fieldContainer = button.parentNode;
    const container = fieldContainer.parentNode;
    container.removeChild(fieldContainer);
  }