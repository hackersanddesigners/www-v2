"use strict";

window.addEventListener('load', () => {
  const controls_template = document.querySelector('#gallery-controls-template')
  for ( const gallery of document.querySelectorAll( '.gallery' ) ) {
    const controls = controls_template.content.cloneNode(true)
    gallery.parentNode.insertBefore( controls, gallery.nextSibling )
    setTimeout(() => {
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
    }, 300)
  }
})
