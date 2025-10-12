// function initializeTableSearch() {
//     $('.searchTable').on('keyup', function() {
//         var value = $(this).val().toLowerCase();
//         var searchColumns = $(this).data('search-columns').toString().split(',');
//         var tableBody = $(this).closest('.scrollableTable').find('table > tbody').eq(1);
//         var tableRows = tableBody.find('tr');
        
//         var hasResults = false;

//         tableRows.each(function() {
//             var row = $(this);
//             var matches = false;
            
//             searchColumns.forEach(function(colIndex) {
//                 var cellText = row.find('td:eq(' + colIndex + ')').text().toLowerCase();
//                 if (cellText.indexOf(value) > -1) {
//                     matches = true;
//                 }
//             });
            
//             row.toggle(matches);
//             if (matches) hasResults = true;
//         });

//         // Remove existing "No data found" row
//         tableBody.find('.no-data').remove();

//         if (!hasResults) {
//             tableBody.append('<tr class="no-data"><td colspan="' + tableRows.first().children('td').length + '" class="text-center">No data found</td></tr>');
//         }

//         if (typeof updateUserCounts === 'function') {
//             updateUserCounts();
//         }
//     });
// }

// $(document).ready(function() {
//     initializeTableSearch();
// });

$(document).ready(function() {
    let typingTimer;
    const doneTypingInterval = 500; // Wait for 500ms after user stops typing

    $('.searchTable').on('input', function() {
        clearTimeout(typingTimer);
        typingTimer = setTimeout(() => {
            $(this).closest('form').submit();
        }, doneTypingInterval);
    });

    // Clear timer if user continues typing
    $('.searchTable').on('keydown', function() {
        clearTimeout(typingTimer);
    });
    setTimeout(function() {
        $('.alert').fadeOut('slow');
      }, 5000);
});