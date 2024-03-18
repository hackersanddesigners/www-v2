"use strict";

function getTableContent() {
  // get all table rows
  return Array.from(document.querySelectorAll("tbody > tr"));
}

function filterBySearch(list) {
  // multi word table filter:
  // - take input query and split it by whitespace
  // - loop over each row of the table and over each column of the row
  // - loop over each token of the input query and check if it is contained
  //   in any of the column.innerText
  // - if yes, display row (as we hide them all at first)
  // 
  // - <https://stackoverflow.com/a/51187579>
  //   <https://dev.to/michelc/search-and-filter-a-table-with-javascript-28mi#comment-14ha2>

  const input = document.querySelector('.table-input-filter');

  input.addEventListener('keyup', (e) => {
    let query = input.value.toLowerCase();
    let queryTokens = query.split(' ');

    for (let i = 0; i < list.length; i++) {
      let row =list[i];
      row.style.display = "none";
      
      let columns = Array.from(row.querySelectorAll('td'));
      if (columns) {
        for (let j = 0; j < columns.length; j++) {
          let column = columns[j];
          
          if (column) {
            let text = column.innerText.toLowerCase();
            
            for (let k = 0; k < queryTokens.length; k++) {
              if (text.indexOf(queryTokens[k]) > -1) {
                row.style.display = "";
                break;
              }

            }
          }
        }
      }
    };

  });

}


window.addEventListener('load', () => {
  let list = getTableContent();
  filterBySearch(list);
})
