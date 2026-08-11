from langchain_text_splitters import RecursiveCharacterTextSplitter

pdf_txt_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1200,
    chunk_overlap=150,
)

csv_splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
)

ppt_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=100,
)


def chunk_pdf_txt(docs):
    return pdf_txt_splitter.split_documents(docs)


def chunk_csv(docs):
    return csv_splitter.split_documents(docs)


def chunk_ppt(docs):
    return ppt_splitter.split_documents(docs)
