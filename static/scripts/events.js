// get current query string from window.location

const $ = a => document.querySelector( a )

const types_menu = $('menu.types')

// get list of available event types
const event_types = Array.from(types_menu.children).map( r => r.firstElementChild.value )

// console.log( Array.from(types_menu.children) )


// add listenerns to radio buttons to change query params
add_radio_listeners()


// fetch query params type
const url_object = new URL(window.location)
const event_type = url_object.searchParams.get( 'type' )


// if a query parameter is passed
if ( event_type ) {


  // check it's in the list
  if ( event_types.includes( event_type ) ) {
    check_radio( event_type )
    create_clr_button()
    filter_events( event_type )

  // event type not found
  } else {
    create_err_msg( 'Event type not found.' )
  }



// if not query parameter is passed
} else {

}



function add_radio_listeners() {
  for ( const radio of types_menu.children ) {
    radio.addEventListener( 'change', e => {
      window.location.search = `?type=${ e.target.value }`
    })
  }
}

function check_radio( val ) {
  $( `input[value="${ val }"]` ).checked = true
}

function create_clr_button() {
  const clr_button = document.createElement( 'button' )
  clr_button.innerHTML = 'Clear filter'
  clr_button.onclick = e => window.location.search = ''
  types_menu.append( clr_button )
}

function create_err_msg( msg ) {
  const err_msg = document.createElement( 'span' )
  err_msg.classList.add('error')
  err_msg.innerHTML = msg
  types_menu.append( err_msg )
}

function filter_events( event_type ) {
   Array.from( $('.events').children )
   .filter( e => e.getAttribute( 'data-type' ) !== event_type )
   .map( e => e.style.display = 'none' )
}
