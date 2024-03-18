"use strict";

window.addEventListener('load', () => {
  const controls_template = document.getElementById('gallery-controls-template')
  for ( const gallery of document.querySelectorAll( '.gallery' ) ) {
    // let controls = controls_template.content.cloneNode(true)
    let controls = document.importNode(controls_template.content, true)
    gallery.parentNode.insertBefore( controls, gallery.nextSibling )
    gallery.nextElementSibling.querySelector( '.right' ).onclick = () => { gallery.scroll({
      // left: gallery.scrollLeft + gallery.offsetWidth - 10 * rem,
      left: gallery.scrollLeft + 0.6 * window.innerWidth ,
      behavior: "smooth"
    })}
    gallery.nextElementSibling.querySelector( '.left' ).onclick = () => { gallery.scroll({
      // left: gallery.scrollLeft - gallery.offsetWidth + 10 * rem,
      left: gallery.scrollLeft - 0.6 * window.innerWidth,
      behavior: "smooth"
    })}
  }
})
