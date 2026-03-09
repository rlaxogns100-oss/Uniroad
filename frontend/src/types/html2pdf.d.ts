declare module 'html2pdf.js' {
  interface Html2PdfInstance {
    set(opt: any): Html2PdfInstance
    from(element: HTMLElement | string): Html2PdfInstance
    save(): Promise<void>
    outputPdf(type?: string): Promise<any>
    toPdf(): Html2PdfInstance
  }

  function html2pdf(): Html2PdfInstance
  export default html2pdf
}
