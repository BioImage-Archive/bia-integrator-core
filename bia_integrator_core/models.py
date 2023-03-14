import pathlib
from typing import Dict, List, Optional, Set, Union, AnyStr

from pydantic import BaseModel
from urllib.parse import urlparse, urlunparse
from pathlib import Path
from ome_types import OME, from_xml
import requests

class BIABaseModel(BaseModel):
    def json(self, ensure_ascii=False, **kwargs):
        """ensure_ascii defaults to False instead of True to handle the common case of non-ascii names"""

        return super().json(ensure_ascii=ensure_ascii, **kwargs)


class ChannelRendering(BIABaseModel):
    colormap_start: List[float]
    colormap_end: List[float]
    scale_factor: float = 1.0


class RenderingInfo(BIABaseModel):
    channel_renders: List[ChannelRendering]
    default_z: Optional[int]
    default_t: Optional[int]


class BIAImageRepresentation(BIABaseModel):
    """A particular representation of a BIAImage. Examples:
    
    * A single HTTP accessible file.
    * Multiple HTTP accessible files, representing different channels, planes and time points.
    * An S3 accessible OME-Zarr.
    * A thumbnail."""
    
    accession_id: str
    image_id: str
    uri: Union[str, List[str]]
    size: int
    type: Optional[str]
    dimensions: Optional[str]
    attributes: Optional[Dict]
    rendering: Optional[RenderingInfo]


class BIAFileRepresentation(BIABaseModel):
    accession_id: str
    file_id: str
    uri: Union[str, List[str]]
    size: int


class BIAFile(BIABaseModel):
    id: str
    original_relpath: pathlib.Path
    original_size: int
    attributes: Dict = {}
    representations: List[BIAFileRepresentation] = []


class FileReference(BIABaseModel):
    """A reference to an externally hosted file."""

    id: str # A unique identifier for the file reference
    name: str # A short descriptive name
    uri: str # URI of the file
    size_in_bytes: Optional[int] # Size of the file
    attributes: Dict = {}


class BIAImage(BIABaseModel):
    """This class represents the abstract concept of an image. Images are
    generated by acquisition by instruments.

    Examples:

    * A single plane bright-field image of a bacterium.
    * A confocal fluorescence image of cells, with two channels.
    * A volume EM stack of a cell.

    Images are distinct from their representation as files, since the same
    image can be represented in different file formats and in some cases
    different file structures.
    """

    id: str
    # TODO - this should be mandatory, but it's a breaking change
    accession_id: Optional[str] = None
    # TODO - rationalise these (name should probably replace original_relpath)
    name: Optional[str]
    original_relpath: pathlib.Path

    dimensions: Optional[str]
    representations: List[BIAImageRepresentation] = []
    attributes: Dict = {}

    @property
    def ome_metadata(self) -> Optional[OME]:
        metadata = self.__dict__.get('ome_metadata', None)
        if metadata is None:
            ngff_rep = [rep for rep in self.representations if rep.type == "ome_ngff"]
            if not ngff_rep:
                return None
            else:
                # If the same image has multiple ngff representations, assume metadata is the same
                ngff_rep = ngff_rep.pop()
                parsed_url = urlparse(ngff_rep.uri)
                ome_metadata_path = Path(parsed_url.path).parent/"OME/METADATA.ome.xml"
                ome_metadata_uri = urlunparse((
                    parsed_url.scheme, parsed_url.netloc, str(ome_metadata_path),
                    None,
                    None,
                    None
                ))

                metadata = BIAImage._ome_xml_url_parse(ome_metadata_uri)
                self.__dict__['ome_metadata'] = metadata

        return metadata

    @classmethod
    def _ome_xml_url_parse(cls, ome_metadata_uri: AnyStr) -> Optional[OME]:    
        r = requests.get(ome_metadata_uri)
        assert r.status_code == 200, f"Error {r.status_code} fetching URI '{ome_metadata_uri}: {r.content}"

        ome_metadata = from_xml(r.content, parser='lxml', validate=False)

        return ome_metadata

class BIAImageAlias(BIABaseModel):
    """An alias for an image - a more convenient way to refer to the image than
    the full accession ID / UUID pair"""

    name: str
    accession_id: str
    image_id: str


class Author(BIABaseModel):
    name: str


class BIAStudy(BIABaseModel):
    accession_id: str
    title: str
    description: str
    authors: Optional[List[Author]] = []
    organism: str
    release_date: str
    
    # FIXME - this should be a list
    imaging_type: Optional[str]
    attributes: Dict = {}
    example_image_uri: str = ""

    file_references: Dict[str, FileReference] = {}

    images: Dict[str, BIAImage] = {}
    archive_files: Dict[str, BIAFile] = {}
    other_files: Dict[str, BIAFile] = {}

    image_aliases: Dict[str, BIAImageAlias] = {}

    tags: Set[str] = set()


class BIACollection(BIABaseModel):
    """A collection of studies with a coherent purpose. Studies can be in 
    multiple collections."""

    name: str
    title: str
    subtitle: str
    description: Optional[str]
    accession_ids: List[str]


class StudyTag(BIABaseModel):
    accession_id: str
    value: str


class StudyAnnotation(BIABaseModel):
    accession_id: str
    key: str
    value: str


class ImageAnnotation(BIABaseModel):
    accession_id: str
    image_id: str
    key: str
    value: str