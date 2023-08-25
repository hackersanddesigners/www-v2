// --

function resetButtons(e) {
  Array.from(tableButtons).map(button => {
    if (button !== e.target) {
      button.removeAttribute("data-dir")
    }
  })
}

function getTableContent() {
  // get all table rows
  return Array.from(document.querySelectorAll("tbody > tr"))
}

function sortByKey(list, key) {
  return () => {

    console.log('sort-by=key =><')

    list.sort((a, b) => {

      let itemA = null
      let itemB = null

      console.log('a, b =>', [a, b])

      if (['title', 'location'].includes(key)) {
        itemA = a.dataset[key].toUpperCase()
        itemB = b.dataset[key].toUpperCase()

      } else if (['dataStart', 'timeStart'].includes(key)) {
        itemA = new Date(a.dataset[key])
        itemB = new Date(b.dataset[key])
      }

      if (itemA < itemB) {
        return -1
      }

      if (itemA > itemB) {
        return 1
      }

      return 0

    }) 

    // e.target.setAttribute("data-dir", "asc")

  }
}

function filterBySearch(list) {

  const input = document.querySelector('.table-input-filter')

  input.addEventListener('keyup', (e) => {
    let query = input.value.toLowerCase()
    
    for (let i = 0; i < list.length; i++) {
      let items = Array.from(list[i].querySelectorAll('td'))

      if (items) {
        for (let j = 0; j < items.length; j++) {
          let match = items[j]
          if (items[j].innerText.toLowerCase().includes(query)) {
            console.log('match =>', [items[j].innerText.toLowerCase(), query, items[j].parentNode])
            items[j].parentNode.classList.add('dn')
          } else {
            console.log('no match =>', [items[j].innerText.toLowerCase(), query, items[j].parentNode])
            items[j].parentNode.classList.remove('dn')
          }
        }
      }

    //   if (item) {
    //     let value = item.textContent || item.innerText

    //     if (value.toUpperCase().indexOf(query) > -1) {
    //       list[i].style.display = '';
    //     } else {
    //       list[i].style.display = 'none';
    //     }
    //   }

    };

  })

}


window.addEventListener('load', () => {
  let list = getTableContent()
  console.log('list =>', list)

  // const tableButtons = Array.from(document.querySelectorAll('th button'));

  // tableButtons.map((button) => {

  //   button.addEventListener('click', (e) => {

  //     // // reset buttons
  //     // tableButtons.map(button => {
  //     //   if (button !== e.target) {
  //     //     button.removeAttribute("data-dir")
  //     //   }
  //     // })

  //     const key = e.target.id
  //     // const dir = e.target.getAttribute("data-dir")

  //     console.log('button =>', [button, e, key, list])
  //     list.sort((a, b) => {

  //       let itemA = null
  //       let itemB = null

  //       if (['title', 'location'].includes(key)) {
  //         itemA = a.dataset[key].toUpperCase()
  //         itemB = b.dataset[key].toUpperCase()

  //       } else if (['dataStart', 'timeStart'].includes(key)) {
  //         itemA = new Date(a.dataset[key])
  //         itemB = new Date(b.dataset[key])
  //       }

  //       console.log('itemA, itemB =>', [itemA, itemB])
  //       console.log('item < itemB =>', itemA < itemB)
  //       console.log('item > itemB =>', itemA > itemB)

  //       if (itemA < itemB) {
  //         return -1
  //       }

  //       if (itemA > itemB) {
  //         return 1
  //       }

  //       return 0

  //     })

  //     // e.target.setAttribute("data-dir", "asc")

  //   })
  // }) 

  filterBySearch(list)

})
